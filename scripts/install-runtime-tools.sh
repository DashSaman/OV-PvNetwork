#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
APP="${PVNETWORK_APP_DIR:-/opt/pvnetwork-panel}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
[[ ${EUID:-$(id -u)} -eq 0 ]] || { echo '[PVNetwork] runtime-tool install requires root' >&2; exit 1; }
install -d -m 0755 /usr/local/sbin /etc/pvnetwork-panel /var/lib/pvnetwork-panel /var/backups/pvnetwork-panel/lifecycle
install -m 0755 "$ROOT/scripts/manage.sh" /usr/local/sbin/pvnetwork
install -m 0755 "$ROOT/scripts/healthcheck.sh" /usr/local/sbin/pvnetwork-panel-healthcheck
install -m 0755 "$ROOT/scripts/pvnetwork-panel-backup" /usr/local/sbin/pvnetwork-panel-backup
install -m 0755 "$ROOT/scripts/pvnetwork-panel-restore-job" /usr/local/sbin/pvnetwork-panel-restore-job
install -m 0755 "$ROOT/scripts/pvnetwork-panel-smoke-test" /usr/local/sbin/pvnetwork-panel-smoke-test
for unit in "$ROOT"/ops/systemd/pvnetwork-panel*.service "$ROOT"/ops/systemd/pvnetwork-panel*.timer; do
  install -m 0644 "$unit" "/etc/systemd/system/$(basename "$unit")"
done
printf '%s\n' "$(cat "$ROOT/VERSION")" > /etc/pvnetwork-panel/version
systemctl daemon-reload
