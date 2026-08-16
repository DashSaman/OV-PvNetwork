#!/usr/bin/env bash
set -Eeuo pipefail
[[ "${EUID:-$(id -u)}" -eq 0 ]] || { echo 'root required' >&2; exit 1; }
. /etc/os-release
case "${ID:-}" in ubuntu|debian) ;; *) echo 'unsupported OS' >&2; exit 1;; esac
for cmd in curl tar python3 systemctl; do command -v "$cmd" >/dev/null || { echo "missing: $cmd" >&2; exit 1; }; done
free_kb="$(df -Pk /opt 2>/dev/null | awk 'NR==2{print $4}')"
[[ "${free_kb:-0}" -ge 1048576 ]] || { echo 'less than 1 GiB free in /opt filesystem' >&2; exit 1; }
echo "PRECHECK=PASS OS=${PRETTY_NAME:-$ID} FREE_KB=$free_kb"
