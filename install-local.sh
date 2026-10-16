#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$SRC/scripts/pvnetwork_install.py" --source "$SRC" "$@"
