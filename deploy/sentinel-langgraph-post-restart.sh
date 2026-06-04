#!/usr/bin/env bash
# After LangGraph systemd start: wait for API, run K8s (+ optional Prom) sync.
# Invoked by sentinel-langgraph.service ExecStartPost.
set -euo pipefail

ROOT="${SENTINEL_ROOT:-/opt/sentinel-x}"
LOG="${SENTINEL_POST_RESTART_LOG:-/var/log/sentinel-post-restart.log}"
ENV_K8S="${SENTINEL_SYNC_ENV:-/etc/sentinel/sync-k8s.env}"
ENV_PROM="${SENTINEL_PROM_SYNC_ENV:-/etc/sentinel/sync-prom.env}"

exec >>"$LOG" 2>&1
echo "=== $(date -Is) sentinel-langgraph-post-restart ==="

LANGGRAPH_API_URL="${LANGGRAPH_API_URL:-http://127.0.0.1:2024}"
if [[ -f "$ENV_K8S" ]]; then
  # shellcheck disable=SC1090
  set -a
  source <(grep -v '^\s*#' "$ENV_K8S" | grep -v '^\s*$' || true)
  set +a
fi
LANGGRAPH_API_URL="${LANGGRAPH_API_URL:-http://127.0.0.1:2024}"

for i in $(seq 1 30); do
  if curl -sf --connect-timeout 2 "${LANGGRAPH_API_URL%/}/ok" >/dev/null; then
    echo "LangGraph ready at $LANGGRAPH_API_URL"
    break
  fi
  sleep 2
  if [[ "$i" -eq 30 ]]; then
    echo "WARN: LangGraph not ready; skip post-restart sync"
    exit 0
  fi
done

if [[ -x /usr/local/bin/sentinel-sync-k8s.sh ]] && [[ -f "$ENV_K8S" ]]; then
  echo "Running K8s sync..."
  env SENTINEL_SYNC_ENV="$ENV_K8S" /usr/local/bin/sentinel-sync-k8s.sh || \
    echo "WARN: K8s sync failed"
fi

if [[ -x /usr/local/bin/sentinel-sync-prom.sh ]] && [[ -f "$ENV_PROM" ]]; then
  echo "Running Prom sync..."
  env SENTINEL_PROM_SYNC_ENV="$ENV_PROM" /usr/local/bin/sentinel-sync-prom.sh || \
    echo "WARN: Prom sync failed"
fi

echo "=== post-restart done ==="
