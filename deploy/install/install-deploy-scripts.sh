#!/bin/bash
# Install deploy scripts to /usr/local/bin and strip CRLF (Windows uploads).
set -eu

ROOT="${SENTINEL_ROOT:-/opt/sentinel-x}"
# shellcheck source=../config/lib/paths.sh
. "${ROOT}/deploy/config/lib/paths.sh"

install_script() {
  local src="$1"
  local dst="$2"
  install -m 755 "$src" "$dst"
  sed -i 's/\r$//' "$dst"
  echo "installed $dst"
}

install_script "${DEPLOY_SYNC}/sync-kubeconfig-for-mcp.sh" /usr/local/bin/sentinel-sync-kubeconfig.sh
install_script "${DEPLOY_SYNC}/sync-k8s.sh" /usr/local/bin/sentinel-sync-k8s.sh
install_script "${DEPLOY_SYNC}/sync-prom.sh" /usr/local/bin/sentinel-sync-prom.sh

for f in "${DEPLOY_CONFIG}/sentinel-config-discover.sh" "${DEPLOY_CONFIG}/sentinel-config-apply.sh" \
  "${DEPLOY_SYSTEMD}/sentinel-langgraph-post-restart.sh"; do
  if [[ -f "$f" ]]; then
    sed -i 's/\r$//' "$f" 2>/dev/null || true
    chmod 755 "$f"
  fi
done
for f in "${DEPLOY_CONFIG}/lib/config-common.sh" "${DEPLOY_CONFIG}/lib/paths.sh"; do
  if [[ -f "$f" ]]; then
    sed -i 's/\r$//' "$f" 2>/dev/null || true
  fi
done

echo "OK: deploy scripts installed (LF normalized)"
