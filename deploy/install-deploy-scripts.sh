#!/usr/bin/env bash
# Legacy wrapper — canonical: deploy/install/install-deploy-scripts.sh
ROOT="${SENTINEL_ROOT:-/opt/sentinel-x}"
exec bash "${ROOT}/deploy/install/install-deploy-scripts.sh" "$@"
