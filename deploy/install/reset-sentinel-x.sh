#!/usr/bin/env bash
# Remove Sentinel-X install artifacts; keep k3s and Docker engine.
#
# Reinstall flow (script lives in the uploaded tarball):
#   tar xzf /tmp/sentinel-x.tgz -C /tmp/sentinel-x-staging ...
#   sudo bash /tmp/sentinel-x-staging/deploy/install/reset-sentinel-x.sh --yes
#   tar xzf /tmp/sentinel-x.tgz -C /opt/sentinel-x ...
#
#   sudo bash deploy/install/reset-sentinel-x.sh [--dry-run] [--yes]
#
set -euo pipefail

SENTINEL_ROOT="${SENTINEL_ROOT:-/opt/sentinel-x}"
DRY_RUN=0
ASSUME_YES=0

usage() {
  cat <<'EOF'
Usage: reset-sentinel-x.sh [--dry-run] [--yes]

Stops sentinel-* systemd units, removes cron/env/state, MCP containers,
and /opt/sentinel-x. Does NOT uninstall k3s or Docker.

  --dry-run   Print actions only
  --yes       Skip confirmation prompt
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=1 ;;
    --yes) ASSUME_YES=1 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown: $1" >&2; usage; exit 1 ;;
  esac
  shift
done

[[ "$(id -u)" -eq 0 ]] || { echo "run as root (sudo)" >&2; exit 1; }

log() { echo "[reset-sentinel-x] $*"; }

do_cmd() {
  if [[ "$DRY_RUN" -eq 1 ]]; then
    log "DRY: $*"
  else
    "$@"
  fi
}

if [[ "$ASSUME_YES" -ne 1 ]] && [[ "$DRY_RUN" -eq 0 ]]; then
  echo "This will remove Sentinel-X from ${SENTINEL_ROOT} and /etc/sentinel/*.env"
  echo "k3s and Docker will be kept. Type 'yes' to continue:"
  read -r confirm
  [[ "$confirm" == "yes" ]] || { log "aborted"; exit 1; }
fi

for unit in sentinel-langgraph sentinel-ui sentinel-api; do
  if systemctl is-active "$unit" >/dev/null 2>&1; then
    log "stopping $unit"
    do_cmd systemctl stop "$unit"
  fi
  if systemctl is-enabled "$unit" >/dev/null 2>&1; then
    log "disabling $unit"
    do_cmd systemctl disable "$unit"
  fi
done

for unit in sentinel-langgraph sentinel-ui sentinel-api; do
  if [[ -f "/etc/systemd/system/${unit}.service" ]]; then
    log "removing /etc/systemd/system/${unit}.service"
    do_cmd rm -f "/etc/systemd/system/${unit}.service"
  fi
done
do_cmd systemctl daemon-reload

if [[ -f /etc/cron.d/sentinel-sync ]]; then
  log "removing /etc/cron.d/sentinel-sync"
  do_cmd rm -f /etc/cron.d/sentinel-sync
fi

if [[ -d /etc/sentinel ]]; then
  log "removing /etc/sentinel/*.env"
  do_cmd rm -f /etc/sentinel/sentinel-x.env /etc/sentinel/sync-k8s.env \
    /etc/sentinel/sync-prom.env /etc/sentinel/sentinel-ui.env \
    /etc/sentinel/sentinel-api.env /etc/sentinel/sentinel-langgraph.env 2>/dev/null || true
fi

for pattern in mcp-k8s mcp-prometheus sentinel-x-mcp; do
  while IFS= read -r cid; do
    [[ -n "$cid" ]] || continue
    log "docker rm -f $cid ($pattern)"
    do_cmd docker rm -f "$cid" 2>/dev/null || true
  done < <(docker ps -aq -f "name=${pattern}" 2>/dev/null || true)
done

if [[ -d /var/lib/sentinel ]]; then
  log "removing /var/lib/sentinel"
  do_cmd rm -rf /var/lib/sentinel
fi

if [[ -d "$SENTINEL_ROOT" ]]; then
  log "removing $SENTINEL_ROOT"
  do_cmd rm -rf "$SENTINEL_ROOT"
fi

log "reset complete (k3s + Docker preserved)"
