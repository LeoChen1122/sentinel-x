#!/usr/bin/env bash
# W7: patrol unhealthy pods and trigger LangGraph inspect.
set -uo pipefail

ENV_FILE="${SENTINEL_SYNC_ENV:-/etc/sentinel/sync-k8s.env}"
LOCK_FILE="${SENTINEL_PATROL_LOCK:-/var/run/sentinel-patrol.lock}"

if [[ -f "$ENV_FILE" ]]; then
  # shellcheck disable=SC1090
  set -a
  source <(sed 's/\r$//' "$ENV_FILE")
  set +a
fi

SENTINEL_ROOT="${SENTINEL_ROOT:-/opt/sentinel-x}"
VENV_PY="${VENV_PYTHON:-${SENTINEL_ROOT}/.venv/bin/python}"
PATROL_SCRIPT="${SENTINEL_ROOT}/agents/langgraph-integration/scripts/live/inspect_patrol_live.py"
LOG_FILE="${SENTINEL_PATROL_LOG:-/var/log/sentinel-patrol.log}"

CLUSTER_ID="${CLUSTER_ID:-k3s-prod}"
NAMESPACE="${NAMESPACE:-kube-system}"
LANGGRAPH_API_URL="${LANGGRAPH_API_URL:-http://127.0.0.1:2024}"

export LANGGRAPH_API_URL
export CLUSTER_ID NAMESPACE SENTINEL_ROOT
export PYTHONPATH="${SENTINEL_ROOT}/agents/langgraph-integration/src${PYTHONPATH:+:${PYTHONPATH}}"
export SENTINEL_PATROL_STATE_PATH="${SENTINEL_PATROL_STATE_PATH:-/var/lib/sentinel/inspect-patrol-state.json}"
[[ -n "${TENANT_ID:-}" ]] && export TENANT_ID
[[ -n "${LANGGRAPH_THREAD_ID:-}" ]] && export LANGGRAPH_THREAD_ID

log() {
  printf '[%s] %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" | tee -a "$LOG_FILE"
}

mkdir -p "$(dirname "$LOG_FILE")" "$(dirname "$SENTINEL_PATROL_STATE_PATH")" 2>/dev/null || true

if [[ ! -x "$VENV_PY" ]]; then
  log "ERROR: python not found: $VENV_PY"
  exit 1
fi
if [[ ! -f "$PATROL_SCRIPT" ]]; then
  log "ERROR: patrol script not found: $PATROL_SCRIPT"
  exit 1
fi

run_patrol() {
  log "START patrol cluster=$CLUSTER_ID namespace=$NAMESPACE"
  if ! curl -sf --connect-timeout 3 "${LANGGRAPH_API_URL%/}/ok" >/dev/null 2>&1; then
    log "WARN: LangGraph not reachable at $LANGGRAPH_API_URL"
  fi
  "$VENV_PY" "$PATROL_SCRIPT" "$@" 2>&1 | while IFS= read -r line; do
    log "$line"
  done
  local rc=${PIPESTATUS[0]}
  case "$rc" in
    0) log "OK patrol finished" ;;
    2) log "SKIP patrol: no candidate or cooldown" ;;
    *) log "ERROR patrol exit code=$rc" ;;
  esac
  return "$rc"
}

if command -v flock >/dev/null 2>&1; then
  exec 9>"$LOCK_FILE"
  if ! flock -n 9; then
    log "SKIP another patrol is running (lock $LOCK_FILE)"
    exit 0
  fi
  run_patrol "$@"
else
  run_patrol "$@"
fi
