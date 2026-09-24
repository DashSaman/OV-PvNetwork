#!/usr/bin/env bash
set -Eeuo pipefail

REPO="DashSaman/OV-PvNetwork"
REF="${PVNETWORK_REF:-v1.0.22}"
TMP="$(mktemp -d /tmp/pvnetwork-panel-install.XXXXXX)"
trap 'rm -rf "$TMP"' EXIT

[[ "${EUID:-$(id -u)}" -eq 0 ]] || { echo '[PVNetwork] ERROR: run as root' >&2; exit 1; }
command -v curl >/dev/null 2>&1 || { apt-get update -y && apt-get install -y curl ca-certificates; }

if [[ "$REF" == v* ]]; then
  URL="https://github.com/${REPO}/archive/refs/tags/${REF}.tar.gz"
else
  URL="https://github.com/${REPO}/archive/refs/heads/${REF}.tar.gz"
fi

curl -fL --retry 5 --connect-timeout 10 "$URL" -o "$TMP/source.tar.gz"
mkdir -p "$TMP/src"
tar -xzf "$TMP/source.tar.gz" -C "$TMP/src" --strip-components=1
chmod +x "$TMP/src/install-local.sh"
exec bash "$TMP/src/install-local.sh" "$@"
