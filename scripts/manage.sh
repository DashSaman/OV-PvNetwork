#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
APP=/opt/pvnetwork-panel
STATE=/etc/pvnetwork-panel
BACKUPS=/var/backups/pvnetwork-panel/lifecycle
# PVNETWORK_REF selects only an immutable release; branch updates are refused.
LIB=/usr/local/lib/pvnetwork-panel
SCRIPT="$LIB/pvnetwork_lifecycle.py"
[[ -f "$SCRIPT" ]] || SCRIPT="$APP/scripts/pvnetwork_lifecycle.py"
[[ -x "$APP/.venv/bin/python" && -f "$SCRIPT" ]] || { echo '[PVNetwork] verified lifecycle runtime missing; recover from the installer checkpoint' >&2; exit 69; }
exec "$APP/.venv/bin/python" "$SCRIPT" "$@"
