# Sentinel-X deploy directory layout (source after SENTINEL_ROOT or ROOT is set).
# Usage: . "${DEPLOY_CONFIG}/lib/paths.sh"

SENTINEL_DEPLOY_ROOT="${SENTINEL_DEPLOY_ROOT:-${SENTINEL_ROOT:-${ROOT:-/opt/sentinel-x}}/deploy}"
DEPLOY_INSTALL="${SENTINEL_DEPLOY_ROOT}/install"
DEPLOY_CONFIG="${SENTINEL_DEPLOY_ROOT}/config"
DEPLOY_SYNC="${SENTINEL_DEPLOY_ROOT}/sync"
DEPLOY_SYSTEMD="${SENTINEL_DEPLOY_ROOT}/systemd"
DEPLOY_PROM="${SENTINEL_DEPLOY_ROOT}/prometheus"
DEPLOY_VERIFY="${SENTINEL_DEPLOY_ROOT}/verify"

# Legacy alias used by some scripts
DEPLOY="${SENTINEL_DEPLOY_ROOT}"
