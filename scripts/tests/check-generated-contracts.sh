#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CHECKER="$ROOT_DIR/scripts/check-generated-contracts.sh"
FIXTURE_TMP="$(mktemp -d)"
trap 'rm -rf -- "$FIXTURE_TMP"' EXIT

NAMES=(openapi.json openapi.ts public-dtos.schema.json sse-events.schema.json sse-events.openapi.json sse.ts)
SOURCES=(
  "$ROOT_DIR/app/contracts/openapi.json"
  "$ROOT_DIR/app/client/src/lib/api/generated/openapi.ts"
  "$ROOT_DIR/app/contracts/public-dtos.schema.json"
  "$ROOT_DIR/app/contracts/sse-events.schema.json"
  "$ROOT_DIR/app/contracts/sse-events.openapi.json"
  "$ROOT_DIR/app/client/src/lib/api/generated/sse.ts"
)

restore() {
  for index in "${!NAMES[@]}"; do cp "${SOURCES[$index]}" "$FIXTURE_TMP/${NAMES[$index]}"; done
}
run_fixture() {
  "$CHECKER" --fixture-artifacts \
    "$FIXTURE_TMP/openapi.json" "$FIXTURE_TMP/openapi.ts" \
    "$FIXTURE_TMP/public-dtos.schema.json" "$FIXTURE_TMP/sse-events.schema.json" \
    "$FIXTURE_TMP/sse-events.openapi.json" "$FIXTURE_TMP/sse.ts"
}

restore
run_fixture >/dev/null
OPENAPI_ARTIFACT="$FIXTURE_TMP/missing-openapi" TYPESCRIPT_ARTIFACT="$FIXTURE_TMP/missing-typescript" run_fixture >/dev/null

for name in "${NAMES[@]}"; do
  restore
  printf '\n// stale\n' >>"$FIXTURE_TMP/$name"
  if run_fixture >/dev/null 2>&1; then
    printf 'stale %s fixture unexpectedly passed\n' "$name" >&2
    exit 1
  fi
done
printf 'generated contract snapshot fixtures: PASS\n'
