# Shared config discovery helpers for Sentinel-X deploy scripts.
# Source: . deploy/config/lib/config-common.sh

config_log() { echo "[sentinel-config] $*"; }

config_die() { echo "[sentinel-config] ERROR: $*" >&2; exit 1; }

config_strip_crlf() {
  local f="$1"
  [[ -f "$f" ]] && sed -i 's/\r$//' "$f" 2>/dev/null || true
}

config_docker_compose() {
  if command -v docker-compose >/dev/null 2>&1; then
    echo docker-compose
  elif docker compose version >/dev/null 2>&1; then
    echo "docker compose"
  else
    config_die "need docker-compose or 'docker compose'"
  fi
}

config_detect_host_ip() {
  local ip=""
  if command -v hostname >/dev/null 2>&1; then
    ip="$(hostname -I 2>/dev/null | awk '{print $1}')"
  fi
  if [[ -z "$ip" ]] && command -v ip >/dev/null 2>&1; then
    ip="$(ip -4 route get 1.1.1.1 2>/dev/null | awk '{for (i=1; i<=NF; i++) if ($i=="src") { print $(i+1); exit }}')"
  fi
  printf '%s' "$ip"
}

config_detect_mcp_container() {
  local image="$1"
  docker ps --filter "ancestor=${image}" --format '{{.Names}}' 2>/dev/null | head -1
}

config_compute_thread_id() {
  local root="$1"
  local cid="$2"
  local tenant="${3:-}"
  "${root}/.venv/bin/python" -c "
import uuid
NS = uuid.UUID('a3b8c9d1-4e5f-6789-abcd-ef0123456789')
tenant = ('${tenant}' or 'default').strip() or 'default'
cid = '${cid}'.strip()
print(uuid.uuid5(NS, f'{tenant}:{cid}'))
"
}

config_is_auto_value() {
  local v="${1:-}"
  [[ -z "$v" ]] || [[ "$v" == "AUTO" ]]
}

config_env_get() {
  local file="$1"
  local key="$2"
  grep -E "^${key}=" "$file" 2>/dev/null | head -1 | cut -d= -f2- || true
}

config_env_set_if_auto() {
  local file="$1"
  local key="$2"
  local value="$3"
  local current
  current="$(config_env_get "$file" "$key")"
  if config_is_auto_value "$current"; then
    if grep -qE "^${key}=" "$file" 2>/dev/null; then
      sed -i "s|^${key}=.*|${key}=${value}|" "$file"
    else
      echo "${key}=${value}" >>"$file"
    fi
    return 0
  fi
  return 1
}

config_detect_prometheus_url() {
  local default_port="${1:-30909}"
  local port="$default_port"
  if command -v kubectl >/dev/null 2>&1; then
    local np
    np="$(kubectl get svc -n monitoring -l app.kubernetes.io/name=prometheus \
      -o jsonpath='{.items[0].spec.ports[?(@.name=="http-web")].nodePort}' 2>/dev/null || true)"
    [[ -n "$np" ]] && port="$np"
  fi
  for try_port in "$port" 30909 9090; do
    if curl -sf --connect-timeout 2 "http://127.0.0.1:${try_port}/-/ready" >/dev/null 2>&1; then
      echo "http://host.docker.internal:${try_port}"
      return 0
    fi
  done
  echo "http://host.docker.internal:${default_port}"
}

config_langgraph_ok() {
  local url="${1:-http://127.0.0.1:2024}"
  curl -sf --connect-timeout 2 "${url%/}/ok" >/dev/null 2>&1
}
