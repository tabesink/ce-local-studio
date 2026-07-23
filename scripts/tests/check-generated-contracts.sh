#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CHECKER="$ROOT_DIR/scripts/check-generated-contracts.sh"
FIXTURE_TMP="$(mktemp -d)"
trap 'rm -rf -- "$FIXTURE_TMP"' EXIT

OPENAPI_FIXTURE="$FIXTURE_TMP/openapi.json"
TYPESCRIPT_FIXTURE="$FIXTURE_TMP/openapi.ts"

cp "$ROOT_DIR/app/contracts/openapi.json" "$OPENAPI_FIXTURE"
cp "$ROOT_DIR/app/client/src/lib/api/generated/openapi.ts" "$TYPESCRIPT_FIXTURE"

"$CHECKER" --fixture-artifacts "$OPENAPI_FIXTURE" "$TYPESCRIPT_FIXTURE" >/dev/null

OPENAPI_ARTIFACT="$FIXTURE_TMP/missing-openapi" \
  TYPESCRIPT_ARTIFACT="$FIXTURE_TMP/missing-typescript" \
  "$CHECKER" >/dev/null

printf ' ' >>"$OPENAPI_FIXTURE"
if "$CHECKER" --fixture-artifacts "$OPENAPI_FIXTURE" "$TYPESCRIPT_FIXTURE" >/dev/null 2>&1; then
  printf 'stale OpenAPI fixture unexpectedly passed\n' >&2
  exit 1
fi

cp "$ROOT_DIR/app/contracts/openapi.json" "$OPENAPI_FIXTURE"
printf '\n// stale\n' >>"$TYPESCRIPT_FIXTURE"
if "$CHECKER" --fixture-artifacts "$OPENAPI_FIXTURE" "$TYPESCRIPT_FIXTURE" >/dev/null 2>&1; then
  printf 'stale TypeScript fixture unexpectedly passed\n' >&2
  exit 1
fi

printf 'generated contract snapshot fixtures: PASS\n'
