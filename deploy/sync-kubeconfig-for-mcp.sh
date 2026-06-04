#!/usr/bin/env bash
# W1-4: Copy k3s kubeconfig to ~/.kube/config for MCP container mount.
# Replaces 127.0.0.1 with host LAN IP or host.docker.internal (container cannot reach host loopback).
set -euo pipefail

K3S_KUBECONFIG="${K3S_KUBECONFIG:-/etc/rancher/k3s/k3s.yaml}"
TARGET="${KUBECONFIG_TARGET:-${HOME}/.kube/config}"
# host-ip | host.docker.internal | none
REPLACE_MODE="${KUBECONFIG_SERVER:-host-ip}"

log() {
  printf '%s\n' "$*" >&2
}

if [[ ! -f "$K3S_KUBECONFIG" ]]; then
  log "ERROR: k3s kubeconfig not found: $K3S_KUBECONFIG"
  log "       run as root or ensure K3S_KUBECONFIG points to a readable file"
  exit 1
fi

mkdir -p "$(dirname "$TARGET")"
cp "$K3S_KUBECONFIG" "$TARGET"
chmod 600 "$TARGET"

detect_host_ip() {
  local ip=""
  if command -v hostname >/dev/null 2>&1; then
    ip="$(hostname -I 2>/dev/null | awk '{print $1}')"
  fi
  if [[ -z "$ip" ]] && command -v ip >/dev/null 2>&1; then
    ip="$(ip -4 route get 1.1.1.1 2>/dev/null | awk '{for (i=1; i<=NF; i++) if ($i=="src") { print $(i+1); exit }}')"
  fi
  printf '%s' "$ip"
}

replace_server() {
  local new_host="$1"
  sed -i "s|https://127.0.0.1:|https://${new_host}:|g" "$TARGET"
  sed -i "s|https://localhost:|https://${new_host}:|g" "$TARGET"
}

case "$REPLACE_MODE" in
  host-ip)
    host_ip="$(detect_host_ip)"
    if [[ -z "$host_ip" ]]; then
      log "WARN: could not detect host LAN IP; left server URL unchanged (may fail in MCP container)"
    else
      replace_server "$host_ip"
      log "OK: server -> https://${host_ip}:6443"
    fi
    ;;
  host.docker.internal)
    replace_server "host.docker.internal"
    log "OK: server -> https://host.docker.internal:6443 (requires compose extra_hosts)"
    ;;
  none|keep)
    log "OK: copied without server URL rewrite (KUBECONFIG_SERVER=none)"
    ;;
  *)
    log "ERROR: unknown KUBECONFIG_SERVER=$REPLACE_MODE (use host-ip, host.docker.internal, none)"
    exit 1
    ;;
esac

log "OK: wrote $TARGET (chmod 600, mode=$REPLACE_MODE)"
grep -E '^\s*server:' "$TARGET" 2>/dev/null || true
