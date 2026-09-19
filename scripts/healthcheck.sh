#!/usr/bin/env bash
set -u
exec 9>/run/pvnetwork-panel-healthcheck.lock
flock -n 9 || exit 0
APP=/opt/pvnetwork-panel
[[ -f "$APP/.env" ]] || exit 0
PORT="$(awk -F= '$1=="PORT"{print $2}' "$APP/.env" | tail -1 | tr -d ' \r')"
PORT="${PORT:-19000}"
check(){ curl -fsS --connect-timeout 1 --max-time 4 "http://127.0.0.1:${PORT}/openapi.json" >/dev/null 2>&1; }
check && exit 0
sleep 5
check && exit 0
logger -t pvnetwork-panel-healthcheck "panel API failed twice; restarting pvnetwork-panel.service"
timeout 35 systemctl restart pvnetwork-panel.service || {
  systemctl kill --kill-who=all --signal=SIGKILL pvnetwork-panel.service 2>/dev/null || true
  systemctl reset-failed pvnetwork-panel.service 2>/dev/null || true
  systemctl start pvnetwork-panel.service
}
