#!/usr/bin/env bash
# Post-install smoke checks for Sentinel-X.
set -euo pipefail

ROOT="${SENTINEL_ROOT:-/opt/sentinel-x}"
ENV_FILE="${SENTINEL_SYNC_ENV:-/etc/sentinel/sync-k8s.env}"
LANGGRAPH_API_URL="${LANGGRAPH_API_URL:-http://127.0.0.1:2024}"
AFTER_RESTART=0
FULL=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --after-restart) AFTER_RESTART=1 ;;
    --full) FULL=1 ;;
    --env-file) ENV_FILE="$2"; shift ;;
    -h|--help)
      echo "Usage: verify-sentinel-x.sh [--after-restart] [--full] [--env-file PATH]"
      echo "  --full   W5-W7: skills dir, sandbox image, patrol script, optional API health"
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
SENTINEL_ROOT="${SENTINEL_ROOT:-$ROOT}"

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

if [[ "$FULL" -eq 1 ]]; then
  echo "[verify] --full: W5-W7 checks..."

  skills_dir="${SENTINEL_SKILLS_DIR:-${SENTINEL_ROOT}/skills}"
  if [[ -d "$skills_dir" ]]; then
    mkdir -p "${skills_dir}/.index" 2>/dev/null || true
    ok "skills dir exists: $skills_dir"
  else
    fail "skills dir missing: $skills_dir"
  fi

  sb_image="${SENTINEL_SANDBOX_IMAGE:-sentinel-x-sandbox:latest}"
  if docker images --format '{{.Repository}}:{{.Tag}}' 2>/dev/null | grep -qF "$sb_image"; then
    ok "sandbox image present: $sb_image"
  else
    fail "sandbox image missing — run: install-sentinel-x.sh --with-sandbox"
  fi

  if [[ -x /usr/local/bin/sentinel-inspect-patrol.sh ]]; then
    ok "sentinel-inspect-patrol.sh installed"
  else
    fail "patrol script missing — run: install-deploy-scripts.sh"
  fi

  if systemctl is-enabled sentinel-api >/dev/null 2>&1; then
    if curl -sf --connect-timeout 3 "http://127.0.0.1:8080/health" >/dev/null 2>&1; then
      ok "sentinel-api /health"
    else
      warn "sentinel-api enabled but /health failed — systemctl status sentinel-api"
    fi
  else
    echo "[verify] SKIP sentinel-api (not enabled)"
  fi

  if [[ -x "$VENV_PY" ]] && [[ -f "${ROOT}/agents/langgraph-integration/scripts/demo/sandbox_demo.py" ]]; then
    echo "[verify] sandbox_demo dry-run (may warn if crash-demo absent)..."
    if env SENTINEL_ROOT="$SENTINEL_ROOT" KUBECONFIG="${K3S_KUBECONFIG:-/etc/rancher/k3s/k3s.yaml}" \
      "$VENV_PY" "${ROOT}/agents/langgraph-integration/scripts/demo/sandbox_demo.py" \
      --pod-name crash-demo --namespace sentinel-sandbox --cluster-id "${CLUSTER_ID:-k3s-prod}" --dry-run 2>/dev/null; then
      ok "sandbox_demo.py ran"
    else
      warn "sandbox_demo failed — apply fixtures: install-sentinel-x.sh --with-fixtures"
    fi
  fi
fi

echo "[verify] All checks passed."
