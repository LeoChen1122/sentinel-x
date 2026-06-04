#!/bin/bash
# Install deploy scripts to /usr/local/bin and strip CRLF (Windows uploads).
set -eu

ROOT="${SENTINEL_ROOT:-/opt/sentinel-x}"
DEPLOY="${ROOT}/deploy"

install_script() {
  local src="$1"
  local dst="$2"
  install -m 755 "$src" "$dst"
  sed -i 's/\r$//' "$dst"
  echo "installed $dst"
}

install_script "${DEPLOY}/sync-kubeconfig-for-mcp.sh" /usr/local/bin/sentinel-sync-kubeconfig.sh
install_script "${DEPLOY}/sync-k8s.sh" /usr/local/bin/sentinel-sync-k8s.sh
install_script "${DEPLOY}/sync-prom.sh" /usr/local/bin/sentinel-sync-prom.sh

for f in sentinel-config-discover.sh sentinel-config-apply.sh sentinel-langgraph-post-restart.sh; do
  if [[ -f "${DEPLOY}/${f}" ]]; then
    sed -i 's/\r$//' "${DEPLOY}/${f}" 2>/dev/null || true
    chmod 755 "${DEPLOY}/${f}"
  fi
done
if [[ -f "${DEPLOY}/lib/config-common.sh" ]]; then
  sed -i 's/\r$//' "${DEPLOY}/lib/config-common.sh" 2>/dev/null || true
fi

echo "OK: deploy scripts installed (LF normalized)"
