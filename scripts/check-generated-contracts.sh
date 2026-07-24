#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_DIR="$ROOT_DIR/app"
CLIENT_DIR="$APP_DIR/client"
CONTRACT_TMP="$(mktemp -d)"
trap 'rm -rf -- "$CONTRACT_TMP"' EXIT

OPENAPI_TMP="$CONTRACT_TMP/openapi.json"
TYPESCRIPT_TMP="$CONTRACT_TMP/openapi.ts"
PUBLIC_SCHEMA_TMP="$CONTRACT_TMP/public-dtos.schema.json"
SSE_SCHEMA_TMP="$CONTRACT_TMP/sse-events.schema.json"
SSE_OPENAPI_TMP="$CONTRACT_TMP/sse-events.openapi.json"
SSE_TYPESCRIPT_TMP="$CONTRACT_TMP/sse.ts"

OPENAPI_ARTIFACT="$APP_DIR/contracts/openapi.json"
TYPESCRIPT_ARTIFACT="$CLIENT_DIR/src/lib/api/generated/openapi.ts"
PUBLIC_SCHEMA_ARTIFACT="$APP_DIR/contracts/public-dtos.schema.json"
SSE_SCHEMA_ARTIFACT="$APP_DIR/contracts/sse-events.schema.json"
SSE_OPENAPI_ARTIFACT="$APP_DIR/contracts/sse-events.openapi.json"
SSE_TYPESCRIPT_ARTIFACT="$CLIENT_DIR/src/lib/api/generated/sse.ts"

if (($# > 0)); then
  if (($# != 7)) || [[ "$1" != "--fixture-artifacts" ]]; then
    printf 'usage: %s [--fixture-artifacts OPENAPI TYPESCRIPT PUBLIC_SCHEMA SSE_SCHEMA SSE_OPENAPI SSE_TYPESCRIPT]\n' "$0" >&2
    exit 2
  fi
  OPENAPI_ARTIFACT="$2"
  TYPESCRIPT_ARTIFACT="$3"
  PUBLIC_SCHEMA_ARTIFACT="$4"
  SSE_SCHEMA_ARTIFACT="$5"
  SSE_OPENAPI_ARTIFACT="$6"
  SSE_TYPESCRIPT_ARTIFACT="$7"
fi

(
  cd "$APP_DIR"
  uv run --frozen --python 3.12 python "$ROOT_DIR/scripts/generate_openapi.py" --output "$OPENAPI_TMP"
  uv run --frozen --python 3.12 python "$ROOT_DIR/scripts/generate_json_schemas.py" \
    --public-output "$PUBLIC_SCHEMA_TMP" \
    --sse-output "$SSE_SCHEMA_TMP" \
    --sse-openapi-output "$SSE_OPENAPI_TMP"
)

compare() {
  local generated="$1" artifact="$2" label="$3" command="$4"
  if ! cmp -s "$generated" "$artifact"; then
    printf 'generated %s is stale; run: %s\n' "$label" "$command" >&2
    exit 1
  fi
}

compare "$OPENAPI_TMP" "$OPENAPI_ARTIFACT" "OpenAPI" "app/.venv/bin/python scripts/generate_openapi.py"
compare "$PUBLIC_SCHEMA_TMP" "$PUBLIC_SCHEMA_ARTIFACT" "public DTO JSON Schema" "app/.venv/bin/python scripts/generate_json_schemas.py"
compare "$SSE_SCHEMA_TMP" "$SSE_SCHEMA_ARTIFACT" "SSE JSON Schema" "app/.venv/bin/python scripts/generate_json_schemas.py"
compare "$SSE_OPENAPI_TMP" "$SSE_OPENAPI_ARTIFACT" "SSE generation view" "app/.venv/bin/python scripts/generate_json_schemas.py"

(
  cd "$CLIENT_DIR"
  ./node_modules/.bin/openapi-typescript "$OPENAPI_TMP" -o "$TYPESCRIPT_TMP"
  ./node_modules/.bin/openapi-typescript "$SSE_OPENAPI_TMP" -o "$SSE_TYPESCRIPT_TMP"
)

compare "$TYPESCRIPT_TMP" "$TYPESCRIPT_ARTIFACT" "TypeScript API" "cd app/client && npm run generate:api"
compare "$SSE_TYPESCRIPT_TMP" "$SSE_TYPESCRIPT_ARTIFACT" "TypeScript SSE contract" "cd app/client && npm run generate:sse"
printf 'generated contract snapshots: PASS\n'
