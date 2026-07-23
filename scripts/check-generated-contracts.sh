#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_DIR="$ROOT_DIR/app"
CLIENT_DIR="$APP_DIR/client"
CONTRACT_TMP="$(mktemp -d)"
trap 'rm -rf -- "$CONTRACT_TMP"' EXIT

OPENAPI_TMP="$CONTRACT_TMP/openapi.json"
TYPESCRIPT_TMP="$CONTRACT_TMP/openapi.ts"
OPENAPI_ARTIFACT="$APP_DIR/contracts/openapi.json"
TYPESCRIPT_ARTIFACT="$CLIENT_DIR/src/lib/api/generated/openapi.ts"

if (($# > 0)); then
  if (($# != 3)) || [[ "$1" != "--fixture-artifacts" ]]; then
    printf 'usage: %s [--fixture-artifacts OPENAPI TYPESCRIPT]\n' "$0" >&2
    exit 2
  fi
  OPENAPI_ARTIFACT="$2"
  TYPESCRIPT_ARTIFACT="$3"
fi

(
  cd "$APP_DIR"
  uv run --frozen --python 3.12 python "$ROOT_DIR/scripts/generate_openapi.py" --output "$OPENAPI_TMP"
)

if ! cmp -s "$OPENAPI_TMP" "$OPENAPI_ARTIFACT"; then
  printf 'generated OpenAPI is stale; run: cd app && uv run --frozen --python 3.12 python ../scripts/generate_openapi.py\n' >&2
  exit 1
fi

(
  cd "$CLIENT_DIR"
  ./node_modules/.bin/openapi-typescript "$OPENAPI_TMP" -o "$TYPESCRIPT_TMP"
)

if ! cmp -s "$TYPESCRIPT_TMP" "$TYPESCRIPT_ARTIFACT"; then
  printf 'generated TypeScript API is stale; run: cd app/client && npm run generate:api\n' >&2
  exit 1
fi

printf 'generated contract snapshots: PASS\n'
