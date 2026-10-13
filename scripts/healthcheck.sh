#!/usr/bin/env bash
set -u
exec 9>/run/pvnetwork-panel-healthcheck.lock
flock -n 9 || exit 0

APP=/opt/pvnetwork-panel
[[ -f "$APP/.env" ]] || exit 0
PANEL_PORT="$(awk -F= '$1=="PORT"{print $2}' "$APP/.env" | tail -1 | tr -d ' \r')"
PANEL_PORT="${PANEL_PORT:-19000}"

check_three() {
  local url="$1"
  for _ in 1 2 3; do
    curl -fsS --connect-timeout 1 --max-time 4 "$url" >/dev/null 2>&1 && return 0
    sleep 5
  done
  return 1
}

service_is_running() {
  [[ "$(systemctl show "$1" -p LoadState --value 2>/dev/null)" == loaded ]] &&
    systemctl is-active --quiet "$1"
}

restart_safely() {
  local service="$1" limit="$2" now retry_after=0
  local cooldown="/run/pvnetwork-panel-healthcheck-${service}.retry-after"
  service_is_running "$service" || return 0
  now="$(date +%s)"
  if [[ -f "$cooldown" ]]; then
    read -r retry_after < "$cooldown" || retry_after=0
    [[ "$retry_after" =~ ^[0-9]+$ ]] || retry_after=0
  fi
  (( now < retry_after )) && return 0
  # Record the attempt before restarting so an interrupted check cannot loop.
  printf '%s\n' "$((now + 300))" > "$cooldown" || return 1
  timeout "$limit" systemctl try-restart "$service" && return 0
  printf '%s\n' "$((now + 900))" > "$cooldown" || true
  logger -t pvnetwork-panel-healthcheck "bounded restart failed for ${service}; manual diagnosis required, retry delayed"
  return 1
}

if service_is_running pvnetwork-panel.service && ! check_three "http://127.0.0.1:${PANEL_PORT}/healthz"; then
  logger -t pvnetwork-panel-healthcheck "panel API failed three checks; restarting pvnetwork-panel.service"
  restart_safely pvnetwork-panel.service 35 || exit 1
fi

NODE_ENV=/opt/ov-node/.env
[[ -f "$NODE_ENV" ]] || exit 0
NODE_PORT="$(awk -F= '
  /^[[:space:]]*SERVICE_PORT[[:space:]]*=/ {
    value=substr($0,index($0,"=")+1)
    gsub(/^[[:space:]"\047]+|[[:space:]"\047]+$/, "", value)
    print value
  }
' "$NODE_ENV" 2>/dev/null | tail -1)"
NODE_PORT="${NODE_PORT:-9090}"
NODE_KEY="$(awk -F= '
  /^[[:space:]]*API_KEY[[:space:]]*=/ {
    value=substr($0,index($0,"=")+1)
    gsub(/^[[:space:]"\047]+|[[:space:]"\047]+$/, "", value)
    print value
  }
' "$NODE_ENV" 2>/dev/null | tail -1)"

[[ -n "$NODE_KEY" ]] || exit 0
service_is_running ov-node.service || exit 0

check_node_three() {
  [[ -n "$NODE_KEY" ]] || return 1
  local payload='{"tunnel_address":"127.0.0.1","protocol":"udp","ovpn_port":1194,"set_new_setting":false}'
  local http_status curl_failed
  for _ in 1 2 3; do
    curl_failed=0
    http_status="$(curl -sS --connect-timeout 1 --max-time 4 \
      -X GET \
      -H "key: ${NODE_KEY}" \
      -H 'content-type: application/json' \
      --data "$payload" \
      -o /dev/null -w '%{http_code}' \
      "http://127.0.0.1:${NODE_PORT}/sync/status" 2>/dev/null)" || curl_failed=1
    # Client/auth/schema errors require configuration diagnosis, not a restart.
    [[ "$http_status" == 4?? ]] && return 2
    [[ "$http_status" == 200 && "$curl_failed" == 0 ]] && return 0
    sleep 5
  done
  return 1
}

check_node_three
node_health_status=$?
if [[ "$node_health_status" == 2 ]]; then
  logger -t pvnetwork-panel-healthcheck "node health request rejected; check credentials/API contract, no repair attempted"
  exit 1
elif [[ "$node_health_status" != 0 ]]; then
  logger -t pvnetwork-panel-healthcheck "external node API failed three authenticated status checks on port ${NODE_PORT}; restarting ov-node.service"
  restart_safely ov-node.service 30 || exit 1
fi
