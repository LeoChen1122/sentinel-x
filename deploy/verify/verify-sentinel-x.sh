#!/usr/bin/env bash
# Post-install smoke checks for Sentinel-X.
set -euo pipefail

ROOT="${SENTINEL_ROOT:-/opt/sentinel-x}"
ENV_FILE="${SENTINEL_SYNC_ENV:-/etc/sentinel/sync-k8s.env}"
LANGGRAPH_API_URL="${LANGGRAPH_API_URL:-http://127.0.0.1:2024}"
AFTER_RESTART=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --after-restart) AFTER_RESTART=1 ;;
    --env-file) ENV_FILE="$2"; shift ;;
    -h|--help)
      echo "Usage: verify-sentinel-x.sh [--after-restart] [--env-file PATH]"
      exit 0
      ;;
    *) echo "Unknown: $1" >&2; exit 1 ;;
  esac
  shift
done

if [[ -f "$ENV_FILE" ]]; then
  # shellcheck disable=SC1090
  set -a
  source <(sed 's/\r$//' "$ENV_FILE")
  set +a
fi

LANGGRAPH_API_URL="${LANGGRAPH_API_URL:-http://127.0.0.1:2024}"
VENV_PY="${VENV_PYTHON:-${ROOT}/.venv/bin/python}"

ok() { echo "[verify] OK: $*"; }
warn() { echo "[verify] WARN: $*"; }
fail() { echo "[verify] FAIL: $*" >&2; exit 1; }

if [[ "$AFTER_RESTART" -eq 1 ]]; then
  echo "[verify] --after-restart: LangGraph uses in-memory checkpoint; graph may be empty until sync."
  echo "[verify] Fix: sudo /usr/local/bin/sentinel-sync-k8s.sh  (or wait for cron / ExecStartPost hook)"
fi

echo "[verify] LangGraph health..."
curl -sf "${LANGGRAPH_API_URL%/}/ok" >/dev/null || fail "curl ${LANGGRAPH_API_URL}/ok"
ok "curl ${LANGGRAPH_API_URL}/ok"

if [[ -n "${MCP_CONTAINER:-}" ]]; then
  echo "[verify] MCP K8s pods in ${NAMESPACE:-kube-system}..."
  n="$(docker exec "$MCP_CONTAINER" python -c \
    "from tools.k8s_get_pods import k8s_get_pods; print(len(k8s_get_pods('${NAMESPACE:-kube-system}')))" 2>/dev/null || echo 0)"
  [[ "${n:-0}" -gt 0 ]] && ok "MCP returned $n pods" || fail "MCP pod list empty or error"
fi

count=0
if [[ -n "${LANGGRAPH_THREAD_ID:-}" ]] && [[ -x "$VENV_PY" ]]; then
  echo "[verify] list_pods via LangGraph..."
  count="$("$VENV_PY" -c "
import os, sys
sys.path.insert(0, '${ROOT}/agents/langgraph-integration/src')
from clients.langgraph_client import query_sentinel, get_langgraph_client
c = get_langgraph_client()
r = query_sentinel('list_pods', thread_id=os.environ['LANGGRAPH_THREAD_ID'], client=c,
                   cluster_id=os.environ.get('CLUSTER_ID','k3s-prod'),
                   namespace=os.environ.get('NAMESPACE','kube-system'))
print(r.get('count', 0))
" 2>/dev/null || echo 0)"
  ok "list_pods count=$count"
  if [[ "${count:-0}" -eq 0 ]]; then
    if [[ "$AFTER_RESTART" -eq 1 ]]; then
      warn "list_pods count=0 after restart — run: sudo /usr/local/bin/sentinel-sync-k8s.sh"
      exit 1
    fi
    warn "list_pods count=0 — run sync or check thread_id in $ENV_FILE"
  fi
else
  echo "[verify] SKIP list_pods (set LANGGRAPH_THREAD_ID in $ENV_FILE)"
fi

systemctl is-active sentinel-langgraph >/dev/null 2>&1 && ok "sentinel-langgraph active" || \
  warn "sentinel-langgraph not active"

echo "[verify] All checks passed."
