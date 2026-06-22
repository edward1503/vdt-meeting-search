#!/usr/bin/env sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$ROOT_DIR"

PYTHON_BIN=${PYTHON:-python}
EMBEDDING_HOST=${EMBEDDING_HOST:-0.0.0.0}
EMBEDDING_PORT=${EMBEDDING_PORT:-8010}
EMBEDDING_DEVICE=${EMBEDDING_DEVICE:-cuda}
EMBEDDING_HEALTH_URL="http://127.0.0.1:${EMBEDDING_PORT}/health"
EMBEDDING_EMBED_URL="http://127.0.0.1:${EMBEDDING_PORT}/embed"
API_BASE_URL=${API_BASE_URL:-http://127.0.0.1:8001}
COMPOSE_SERVICES="elasticsearch redis api frontend"
PID_FILE=".runtime/embedding_server.pid"
STDOUT_LOG="logs/embedding_server.stdout.log"
STDERR_LOG="logs/embedding_server.stderr.log"

log() {
  printf '%s\n' "[start] $*"
}

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    printf '%s\n' "Missing required command: $1" >&2
    exit 1
  fi
}

pid_command_line() {
  pid="$1"
  if command -v powershell.exe >/dev/null 2>&1; then
    powershell.exe -NoProfile -Command "\$p = Get-CimInstance Win32_Process -Filter 'ProcessId=$pid'; if (\$p) { \$p.CommandLine }" 2>/dev/null | tr -d '\r'
  else
    ps -p "$pid" -o args= 2>/dev/null || true
  fi
}

stop_process() {
  pid="$1"
  if command -v powershell.exe >/dev/null 2>&1; then
    powershell.exe -NoProfile -Command "Stop-Process -Id $pid -Force" >/dev/null 2>&1 || true
  else
    kill "$pid" >/dev/null 2>&1 || true
  fi
}

is_port_open() {
  "$PYTHON_BIN" - "$EMBEDDING_PORT" <<'PY'
import socket
import sys

port = int(sys.argv[1])
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
    sock.settimeout(0.5)
    sys.exit(0 if sock.connect_ex(("127.0.0.1", port)) == 0 else 1)
PY
}

health_ready() {
  "$PYTHON_BIN" - "$EMBEDDING_HEALTH_URL" <<'PY'
import json
import sys
import urllib.request

try:
    with urllib.request.urlopen(sys.argv[1], timeout=2) as response:
        payload = json.loads(response.read().decode("utf-8"))
except Exception:
    sys.exit(1)
sys.exit(0 if payload.get("status") == "ok" else 1)
PY
}

wait_for_health() {
  for _ in $(seq 1 120); do
    if health_ready; then
      return 0
    fi
    sleep 1
  done
  printf '%s\n' "Embedding service did not become healthy. See $STDERR_LOG" >&2
  exit 1
}

warm_embedding_model() {
  model_id="$1"
  expected_dim="$2"
  text="$3"
  "$PYTHON_BIN" - "$EMBEDDING_EMBED_URL" "$model_id" "$expected_dim" "$text" <<'PY'
import json
import sys
import urllib.request

url, model_id, expected_dim, text = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4]
body = {"text": text}
if model_id:
    body["model_id"] = model_id
request = urllib.request.Request(
    url,
    data=json.dumps(body).encode("utf-8"),
    headers={"Content-Type": "application/json"},
    method="POST",
)
with urllib.request.urlopen(request, timeout=120) as response:
    payload = json.loads(response.read().decode("utf-8"))
dim = len(payload.get("embedding", []))
if dim != expected_dim:
    raise SystemExit(f"expected {expected_dim} dims for {model_id or 'hotpotqa'}, got {dim}")
print(f"{model_id or 'hotpotqa'} dim={dim}")
PY
}

wait_for_api() {
  for _ in $(seq 1 120); do
    if "$PYTHON_BIN" - "$API_BASE_URL/datasets" <<'PY'
import json
import sys
import urllib.request

try:
    with urllib.request.urlopen(sys.argv[1], timeout=2) as response:
        payload = json.loads(response.read().decode("utf-8"))
except Exception:
    sys.exit(1)
sys.exit(0 if payload.get("datasets") else 1)
PY
    then
      return 0
    fi
    sleep 1
  done
  printf '%s\n' "API did not become ready at $API_BASE_URL" >&2
  exit 1
}

smoke_search() {
  dataset="$1"
  method="$2"
  query="$3"
  "$PYTHON_BIN" - "$API_BASE_URL/datasets/$dataset/search" "$method" "$query" <<'PY'
import json
import sys
import urllib.request

url, method, query = sys.argv[1], sys.argv[2], sys.argv[3]
body = json.dumps({"query": query, "method": method, "top_k": 3}).encode("utf-8")
request = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
with urllib.request.urlopen(request, timeout=180) as response:
    payload = json.loads(response.read().decode("utf-8"))
results = payload.get("results", [])
if not results:
    raise SystemExit(f"{method} returned no results")
print(f"{method} results={len(results)}")
PY
}

missing_compose_services() {
  existing_services=$(docker compose ps --all --services 2>/dev/null || true)
  missing=""
  for service in $COMPOSE_SERVICES; do
    found=0
    for existing in $existing_services; do
      if [ "$existing" = "$service" ]; then
        found=1
        break
      fi
    done
    if [ "$found" -eq 0 ]; then
      missing="$missing $service"
    fi
  done
  printf '%s' "${missing# }"
}

require_command docker
require_command "$PYTHON_BIN"
require_command nvidia-smi

mkdir -p .runtime logs

log "Checking NVIDIA GPU"
nvidia-smi >/dev/null

if [ -f "$PID_FILE" ]; then
  old_pid=$(cat "$PID_FILE")
  if [ -n "$old_pid" ] && kill -0 "$old_pid" >/dev/null 2>&1; then
    old_cmd=$(pid_command_line "$old_pid")
    case "$old_cmd" in
      *scripts/embedding_server.py*)
        log "Stopping stale embedding server pid $old_pid"
        stop_process "$old_pid"
        sleep 2
        ;;
      *)
        printf '%s\n' "PID file points to a non-embedding process: $old_pid" >&2
        exit 1
        ;;
    esac
  fi
  rm -f "$PID_FILE"
fi

if is_port_open; then
  if health_ready; then
    log "Reusing healthy embedding service on port $EMBEDDING_PORT"
  else
    printf '%s\n' "Port $EMBEDDING_PORT is occupied by a non-embedding service" >&2
    exit 1
  fi
else
  log "Starting host GPU embedding service on port $EMBEDDING_PORT"
  CUDA_VISIBLE_DEVICES=${CUDA_VISIBLE_DEVICES:-0} "$PYTHON_BIN" scripts/embedding_server.py \
    --host "$EMBEDDING_HOST" \
    --port "$EMBEDDING_PORT" \
    --device "$EMBEDDING_DEVICE" \
    --no-warmup \
    >"$STDOUT_LOG" 2>"$STDERR_LOG" &
  echo "$!" >"$PID_FILE"
fi

wait_for_health
log "Warming HotpotQA embedding model"
warm_embedding_model "" 384 "what connects alpha and beta"
log "Warming VimQA embedding model"
warm_embedding_model "vimqa" 768 "xin chao"

missing_services=$(missing_compose_services)
if [ -n "$missing_services" ]; then
  log "Missing Docker Compose containers:$missing_services; building services"
  docker compose up -d --build $COMPOSE_SERVICES
else
  log "Docker Compose containers already exist; starting without rebuild"
  docker compose up -d $COMPOSE_SERVICES
fi

log "Checking API container can reach host embedding service"
docker compose exec -T api python -c "import json, urllib.request; print(json.load(urllib.request.urlopen('http://host.docker.internal:${EMBEDDING_PORT}/health', timeout=5))['status'])"

log "Waiting for dataset API"
wait_for_api

log "Smoke testing HotpotQA tv_hybrid"
smoke_search "hotpotqa" "tv_hybrid" "Who founded Microsoft?"

log "Startup complete"
log "Frontend: http://localhost:3001"
log "FastAPI:  http://localhost:8001/docs"
