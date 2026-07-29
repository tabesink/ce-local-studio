#!/usr/bin/env bash
# Context Engine local demo entrypoint (P12-07 U11).
# Default: Compose full-stack demo (base + MinIO + live runtime overlay).
# Host-native hot reload: CE_DEV_MODE=host bash scripts/dev.sh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_DIR="$ROOT_DIR/app"
ENV_FILE="${ENV_FILE:-$APP_DIR/.env.stack.local}"
EXAMPLE_ENV="$APP_DIR/.env.stack.example"
PYTHON_BIN="${PYTHON_BIN:-$ROOT_DIR/.venv/bin/python}"
CE_DEV_MODE="${CE_DEV_MODE:-compose}"
COMPOSE_TIMEOUT_SECONDS="${COMPOSE_TIMEOUT_SECONDS:-300}"
STACK_LIVE_RUNTIME_ROOT_DEFAULT="${CE_STACK_LIVE_RUNTIME_ROOT:-$APP_DIR/.data/domain-runtimes}"

COMPOSE_FILES=(
  -f compose.stack.yml
  -f compose.stack.minio.yml
  -f compose.stack.live.yml
)

usage() {
  cat <<'EOF'
Usage: bash scripts/dev.sh [--help]

Default path (CE_DEV_MODE=compose):
  Bring up the local demo Compose matrix (PostgreSQL, migrate, bootstrap,
  API, worker, frontend/BFF, MinIO, live private runtime/controller support).

Host-native hot reload (not the full-stack demo):
  CE_DEV_MODE=host bash scripts/dev.sh

Environment:
  ENV_FILE                 Default: app/.env.stack.local
  COMPOSE_TIMEOUT_SECONDS  Readiness wait (default 300)
  CE_STACK_LIVE_RUNTIME_ROOT  Host-absolute runtime bind (created if absent)
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

load_env_file() {
  local file="$1"
  [[ -f "$file" ]] || return 0
  while IFS= read -r line || [[ -n "$line" ]]; do
    line="${line%%#*}"
    line="${line#"${line%%[![:space:]]*}"}"
    line="${line%"${line##*[![:space:]]}"}"
    [[ -z "$line" || "$line" != *"="* ]] && continue
    local key="${line%%=*}"
    local value="${line#*=}"
    key="${key%"${key##*[![:space:]]}"}"
    value="${value#"${value%%[![:space:]]*}"}"
    value="${value%"${value##*[![:space:]]}"}"
    value="${value%\"}"
    value="${value#\"}"
    value="${value%\'}"
    value="${value#\'}"
    if [[ -z "${!key:-}" ]]; then
      export "$key=$value"
    fi
  done < "$file"
}

is_placeholder_value() {
  local value="$1"
  [[ -z "$value" || "$value" == "<set-locally>" || "$value" == *"<set locally"* ]]
}

ensure_env_file() {
  if [[ ! -f "$ENV_FILE" ]]; then
    if [[ ! -f "$EXAMPLE_ENV" ]]; then
      echo "Missing $EXAMPLE_ENV" >&2
      exit 1
    fi
    cp "$EXAMPLE_ENV" "$ENV_FILE"
    chmod 600 "$ENV_FILE" 2>/dev/null || true
    echo "Created $ENV_FILE from example. Replace placeholder secrets before continuing."
  fi
}

upsert_env_key() {
  local key="$1"
  local value="$2"
  local tmp
  tmp="$(mktemp)"
  if grep -q "^${key}=" "$ENV_FILE" 2>/dev/null; then
    # Preserve existing non-empty values.
    local current
    current="$(grep "^${key}=" "$ENV_FILE" | head -n1 | cut -d= -f2-)"
    if ! is_placeholder_value "$current"; then
      rm -f "$tmp"
      return 0
    fi
    awk -v k="$key" -v v="$value" 'BEGIN{FS=OFS="="} $1==k{$0=k"="v} {print}' "$ENV_FILE" >"$tmp"
  else
    cat "$ENV_FILE" >"$tmp"
    printf '%s=%s\n' "$key" "$value" >>"$tmp"
  fi
  mv "$tmp" "$ENV_FILE"
  chmod 600 "$ENV_FILE" 2>/dev/null || true
}

ensure_graph_ref_key() {
  load_env_file "$ENV_FILE"
  local current="${CE_GRAPH_REF_KEY:-}"
  if ! is_placeholder_value "$current" && [[ "${#current}" -ge 32 ]]; then
    return 0
  fi
  # 32 cryptographically random bytes as base64url; never echo the value.
  local generated
  generated="$(
    "$PYTHON_BIN" - <<'PY'
import base64, secrets
print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode("ascii").rstrip("="))
PY
  )"
  upsert_env_key "CE_GRAPH_REF_KEY" "$generated"
  export CE_GRAPH_REF_KEY="$generated"
  echo "Generated CE_GRAPH_REF_KEY into ${ENV_FILE} (mode 0600; value not printed)."
}

require_command() {
  local name="$1"
  if ! command -v "$name" >/dev/null 2>&1; then
    echo "Missing required command: $name" >&2
    exit 1
  fi
}

preflight_compose() {
  require_command docker
  if ! docker compose version >/dev/null 2>&1; then
    echo "Docker Compose plugin is required (docker compose)." >&2
    exit 1
  fi
  if [[ ! -x "$PYTHON_BIN" ]]; then
    echo "Missing Python venv at $PYTHON_BIN" >&2
    echo "Run: python3 -m venv .venv && .venv/bin/python -m pip install -e '.[test]'" >&2
    exit 1
  fi
  ensure_env_file
  ensure_graph_ref_key
  load_env_file "$ENV_FILE"

  local required=(
    POSTGRES_DB
    POSTGRES_USER
    POSTGRES_PASSWORD
    CE_ADMIN_USERNAME
    CE_ADMIN_PASSWORD
    CONFIG_ENCRYPTION_KEY
    CE_CSRF_SIGNING_KEY
    CE_GRAPH_REF_KEY
    MINIO_ROOT_USER
    MINIO_ROOT_PASSWORD
  )
  local missing=()
  local placeholder=()
  local key value
  for key in "${required[@]}"; do
    value="${!key:-}"
    if is_placeholder_value "$value"; then
      placeholder+=("$key")
    elif [[ -z "$value" ]]; then
      missing+=("$key")
    fi
  done
  if ((${#placeholder[@]} > 0 || ${#missing[@]} > 0)); then
    echo "Incomplete local environment in ${ENV_FILE}." >&2
    if ((${#placeholder[@]} > 0)); then
      echo "Replace placeholder values for: ${placeholder[*]}" >&2
    fi
    if ((${#missing[@]} > 0)); then
      echo "Set missing values for: ${missing[*]}" >&2
    fi
    exit 1
  fi

  if [[ "${#CE_GRAPH_REF_KEY}" -lt 32 ]]; then
    echo "CE_GRAPH_REF_KEY must be at least 32 characters." >&2
    exit 1
  fi
  if ! "$PYTHON_BIN" -c "from cryptography.fernet import Fernet; Fernet('${CONFIG_ENCRYPTION_KEY}'.encode('utf-8'))" 2>/dev/null; then
    echo "CONFIG_ENCRYPTION_KEY in ${ENV_FILE} is not a valid Fernet key." >&2
    exit 1
  fi

  mkdir -p "$STACK_LIVE_RUNTIME_ROOT_DEFAULT"
  # Persist absolute path for the live overlay bind mount when unset/placeholder.
  if is_placeholder_value "${CE_STACK_LIVE_RUNTIME_ROOT:-}"; then
    upsert_env_key "CE_STACK_LIVE_RUNTIME_ROOT" "$STACK_LIVE_RUNTIME_ROOT_DEFAULT"
    export CE_STACK_LIVE_RUNTIME_ROOT="$STACK_LIVE_RUNTIME_ROOT_DEFAULT"
  fi
}

compose() {
  (cd "$APP_DIR" && docker compose --env-file "$ENV_FILE" "${COMPOSE_FILES[@]}" "$@")
}

wait_ready() {
  local deadline=$((SECONDS + COMPOSE_TIMEOUT_SECONDS))
  local public_origin="${CE_STACK_PUBLIC_ORIGIN:-http://127.0.0.1:${STACK_FRONTEND_PORT:-3000}}"
  local api_ready="http://127.0.0.1:${STACK_API_PORT:-8000}/health/ready"
  echo "Waiting for API readiness (timeout ${COMPOSE_TIMEOUT_SECONDS}s)…"
  while ((SECONDS < deadline)); do
    if curl -fsS "$api_ready" >/dev/null 2>&1; then
      echo "API ready."
      return 0
    fi
    sleep 2
  done
  echo "Timed out waiting for API readiness at $api_ready" >&2
  echo "Inspect with: (cd app && docker compose --env-file $ENV_FILE ${COMPOSE_FILES[*]} ps)" >&2
  echo "Logs: (cd app && docker compose --env-file $ENV_FILE ${COMPOSE_FILES[*]} logs --tail=200 api worker migrate bootstrap)" >&2
  exit 1
}

print_demo_summary() {
  local public_origin="${CE_STACK_PUBLIC_ORIGIN:-http://127.0.0.1:${STACK_FRONTEND_PORT:-3000}}"
  cat <<EOF

Context Engine local demo is up.

Public application URL: ${public_origin}/login
Configured admin username: ${CE_ADMIN_USERNAME}

Services:
  postgres          private database
  migrate           one-shot schema release step
  bootstrap         one-shot insert-only admin bootstrap
  api               private FastAPI
  worker            private leased workers
  frontend          public Next.js / BFF
  minio / minio-init  governed object store (private)
  live runtime      on-demand per-domain LightRAG containers (no host-published ports)

External integrations (not deployed by this script):
  Reducto parser / model providers — configure write-only credentials in Settings

Useful commands:
  status:  (cd app && docker compose --env-file ${ENV_FILE} ${COMPOSE_FILES[*]} ps)
  logs:    (cd app && docker compose --env-file ${ENV_FILE} ${COMPOSE_FILES[*]} logs -f api worker frontend)
  stop:    (cd app && docker compose --env-file ${ENV_FILE} ${COMPOSE_FILES[*]} stop)

Backup/restore must preserve CE_GRAPH_REF_KEY with PostgreSQL/object versions.
Deliberate key rotation invalidates prior graph node URL selections.

EOF
}

run_compose_demo() {
  preflight_compose
  load_env_file "$ENV_FILE"
  echo "Starting Compose local-demo matrix (base + MinIO + live)…"
  compose up --build -d
  wait_ready
  print_demo_summary
}

# --- Host-native path (explicit only; not the full-stack demo) -----------------

BACKEND_HOST="${BACKEND_HOST:-127.0.0.1}"
BACKEND_PORT_EXPLICIT="${BACKEND_PORT-}"
FRONTEND_PORT_EXPLICIT="${FRONTEND_PORT-}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-3002}"
FRONTEND_MODE="${FRONTEND_MODE:-dev}"
if [[ -n "${CONTEXT_ENGINE_API_BASE:-}" ]]; then
  CONTEXT_ENGINE_API_BASE_SET=1
fi
CONTEXT_ENGINE_API_BASE="${CONTEXT_ENGINE_API_BASE:-http://$BACKEND_HOST:$BACKEND_PORT}"

port_listener_pid() {
  local port="$1"
  ss -tlnp 2>/dev/null | awk -v port=":${port}" '$4 ~ port { if (match($0, /pid=([0-9]+)/, m)) { print m[1]; exit } }'
}

port_in_use() {
  local port="$1"
  [[ -n "$(port_listener_pid "$port" || true)" ]]
}

resolve_dev_port() {
  local name="$1"
  local preferred="$2"
  local explicit="$3"
  local port="$preferred"
  local attempts=0
  local max_attempts=20

  if [[ -n "$explicit" ]]; then
    if port_in_use "$port"; then
      echo "Port ${port} is already in use (${name})." >&2
      exit 1
    fi
    printf '%s' "$port"
    return
  fi

  while port_in_use "$port" && ((attempts < max_attempts)); do
    port=$((port + 1))
    attempts=$((attempts + 1))
  done
  if port_in_use "$port"; then
    echo "Could not find a free ${name} port near ${preferred}." >&2
    exit 1
  fi
  printf '%s' "$port"
}

configure_host_env() {
  ensure_env_file
  ensure_graph_ref_key
  load_env_file "$ENV_FILE"
  local required=(
    POSTGRES_DB POSTGRES_USER POSTGRES_PASSWORD
    CE_ADMIN_USERNAME CE_ADMIN_PASSWORD CONFIG_ENCRYPTION_KEY
  )
  local key value missing=() placeholder=()
  for key in "${required[@]}"; do
    value="${!key:-}"
    if is_placeholder_value "$value"; then placeholder+=("$key")
    elif [[ -z "$value" ]]; then missing+=("$key"); fi
  done
  if ((${#placeholder[@]} > 0 || ${#missing[@]} > 0)); then
    echo "Incomplete local environment in ${ENV_FILE}." >&2
    exit 1
  fi
  if [[ -z "${CONTEXT_ENGINE_DATABASE_URL:-}" ]]; then
    POSTGRES_HOST="${POSTGRES_HOST:-127.0.0.1}"
    POSTGRES_PORT="${POSTGRES_PORT:-5432}"
    export CONTEXT_ENGINE_DATABASE_URL="postgresql+psycopg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@${POSTGRES_HOST}:${POSTGRES_PORT}/${POSTGRES_DB}"
  fi
  export CE_SESSION_COOKIE_SECURE="${CE_SESSION_COOKIE_SECURE:-false}"
  export CONTEXT_ENGINE_TESTING="${CONTEXT_ENGINE_TESTING:-true}"
}

run_host_dev() {
  echo "WARNING: CE_DEV_MODE=host is hot-reload development only — not the full-stack demo path." >&2
  if [[ ! -x "$PYTHON_BIN" ]]; then
    echo "Missing Python venv at $PYTHON_BIN" >&2
    exit 1
  fi
  if [[ ! -d "$APP_DIR/client/node_modules" ]]; then
    echo "Missing frontend dependencies. Run: cd app/client && npm ci" >&2
    exit 1
  fi
  configure_host_env
  BACKEND_PORT="$(resolve_dev_port "backend" "$BACKEND_PORT" "$BACKEND_PORT_EXPLICIT")"
  FRONTEND_PORT="$(resolve_dev_port "frontend" "$FRONTEND_PORT" "$FRONTEND_PORT_EXPLICIT")"
  export CONTEXT_ENGINE_API_BASE="http://$BACKEND_HOST:$BACKEND_PORT"

  local backend_pid="" frontend_pid=""
  cleanup() {
    [[ -n "$frontend_pid" ]] && kill "$frontend_pid" 2>/dev/null || true
    [[ -n "$backend_pid" ]] && kill "$backend_pid" 2>/dev/null || true
  }
  trap cleanup EXIT INT TERM

  echo "Migrating database..."
  (cd "$APP_DIR" && "$PYTHON_BIN" -m context_engine.migrate_release)
  (cd "$APP_DIR" && "$PYTHON_BIN" -m context_engine.bootstrap_admin)

  echo "Starting backend on http://$BACKEND_HOST:$BACKEND_PORT"
  (cd "$APP_DIR" && "$PYTHON_BIN" -m uvicorn context_engine.app:create_app --factory --reload --reload-dir context_engine --reload-dir migrations --host "$BACKEND_HOST" --port "$BACKEND_PORT") &
  backend_pid=$!
  echo "Starting frontend on http://localhost:$FRONTEND_PORT"
  (
    cd "$APP_DIR/client"
    WATCHPACK_POLLING="${WATCHPACK_POLLING:-true}" \
    CHOKIDAR_USEPOLLING="${CHOKIDAR_USEPOLLING:-true}" \
    CONTEXT_ENGINE_API_BASE="$CONTEXT_ENGINE_API_BASE" npm run dev -- --webpack -p "$FRONTEND_PORT"
  ) &
  frontend_pid=$!
  echo
  echo "Host-native (not full demo): Frontend http://localhost:$FRONTEND_PORT"
  echo "Stop with Ctrl+C."
  wait -n "$backend_pid" "$frontend_pid"
}

case "$CE_DEV_MODE" in
  compose|demo|"")
    run_compose_demo
    ;;
  host)
    run_host_dev
    ;;
  *)
    echo "Unknown CE_DEV_MODE=$CE_DEV_MODE (use compose or host)." >&2
    exit 1
    ;;
esac
