#!/usr/bin/env bash
set -u -o pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_DIR="$ROOT_DIR/app"
FAILURES=0

run_check() {
  local name="$1"
  shift
  printf '\n==> %s\n' "$name"
  if "$@"; then
    printf 'PASS: %s\n' "$name"
  else
    printf 'FAIL: %s\n' "$name" >&2
    FAILURES=$((FAILURES + 1))
  fi
}

run_check "phase-scope documentation" bash "$ROOT_DIR/scripts/check-doc-phase-scope.sh"
run_check "phase-scope checker fixtures" bash "$ROOT_DIR/scripts/tests/check-doc-phase-scope.sh"
run_check "Python lock integrity" bash -c "cd '$APP_DIR' && uv lock --check"
run_check "backend package import" bash -c "cd '$APP_DIR' && uv run --frozen --python 3.12 python -c 'import context_engine'"
run_check "backend lint" bash -c "cd '$APP_DIR' && uv run --frozen --python 3.12 --extra test ruff check context_engine"
# Privacy scans (P8-01 audit, P8-02 logs/metrics, P8-03 cross-sink) ride default pytest.
# Disposable PostgreSQL suites skip unless CONTEXT_ENGINE_ALLOW_DISPOSABLE_DATABASE_TESTS=1;
# CI runs them in the separate verify-postgresql job (pytest -m postgresql).
run_check "backend tests" bash -c "cd '$APP_DIR' && uv run --frozen --python 3.12 --extra test pytest"
run_check "frontend dependency lock" bash -c "cd '$APP_DIR/client' && npm ci"
run_check "generated contract snapshots" bash "$ROOT_DIR/scripts/check-generated-contracts.sh"
run_check "generated contract snapshot fixtures" bash "$ROOT_DIR/scripts/tests/check-generated-contracts.sh"
# P12-06 PR-light pins only (locks/heads/contracts). Release-full digests/SBOM stay
# operator/release-job — do not require Docker image matrix or Syft here.
run_check "release manifest PR-light" bash -c "cd '$APP_DIR' && python -m scripts.generate_release_manifest --profile pr --check '$ROOT_DIR/docs/releases/release-manifest.json'"
run_check "release manifest unit fixtures" bash "$ROOT_DIR/scripts/tests/check-release-manifest.sh"
run_check "frontend typecheck" bash -c "cd '$APP_DIR/client' && npm run typecheck"
run_check "frontend tests" bash -c "cd '$APP_DIR/client' && npm test"
run_check "frontend production build" bash -c "cd '$APP_DIR/client' && npm run build"
run_check "backend Docker build" bash -c "cd '$APP_DIR' && docker build --target runtime -t context-engine-verify ."
run_check "Compose configuration" bash -c "cd '$APP_DIR' && POSTGRES_DB=verify POSTGRES_USER=verify POSTGRES_PASSWORD=verify CE_ADMIN_USERNAME=verify CE_ADMIN_PASSWORD=verify CONFIG_ENCRYPTION_KEY=verify-encryption-key-not-csrf!!!! CE_STACK_PUBLIC_ORIGIN=http://127.0.0.1:3000 CE_INTERNAL_HOSTS=api CE_TRUSTED_BFF_PEERS=172.30.55.10/32 CE_CSRF_SIGNING_KEY=verify-csrf-signing-key-32bytes-min!! docker compose -f compose.stack.yml config --quiet"

if ((FAILURES > 0)); then
  printf '\nverification: FAIL (%d check(s))\n' "$FAILURES" >&2
  exit 1
fi

printf '\nverification: PASS\n'
