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

restart_safely() {
  local service="$1" limit="$2"
  timeout "$limit" systemctl restart "$service" && return 0
  systemctl kill --kill-who=all --signal=SIGKILL "$service" 2>/dev/null || true
  sleep 2
  systemctl reset-failed "$service" 2>/dev/null || true
  systemctl start "$service"
}

if ! check_three "http://127.0.0.1:${PANEL_PORT}/healthz"; then
  logger -t pvnetwork-panel-healthcheck "panel API failed three checks; restarting pvnetwork-panel.service"
  restart_safely pvnetwork-panel.service 35
fi

NODE_ENV=/opt/ov-node/.env
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

check_node_three() {
  [[ -n "$NODE_KEY" ]] || return 1
  local payload='{"tunnel_address":"127.0.0.1","protocol":"udp","ovpn_port":1194,"set_new_setting":false}'
  for _ in 1 2 3; do
    curl -fsS --connect-timeout 1 --max-time 4 \
      -X GET \
      -H "key: ${NODE_KEY}" \
      -H 'content-type: application/json' \
      --data "$payload" \
      "http://127.0.0.1:${NODE_PORT}/sync/status" >/dev/null 2>&1 && return 0
    sleep 5
  done
  return 1
}

if ! check_node_three; then
  logger -t pvnetwork-panel-healthcheck "external node API failed three authenticated status checks on port ${NODE_PORT}; restarting ov-node.service"
  restart_safely ov-node.service 30
fi
