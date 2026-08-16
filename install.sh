#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT="OV-PvNetwork"
REPO="DashSaman/OV-PvNetwork"
REF="${OVPV_REF:-main}"
TMP="$(mktemp -d /tmp/ov-pvnetwork-install.XXXXXX)"

cleanup() { rm -rf "$TMP"; }
trap cleanup EXIT

if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
  echo "[ERROR] Run this installer as root." >&2
  exit 1
fi

if [[ -r /etc/os-release ]]; then
  . /etc/os-release
else
  echo "[ERROR] /etc/os-release not found." >&2
  exit 1
fi

case "${ID:-}" in
  ubuntu|debian) ;;
  *)
    echo "[ERROR] Supported distributions: Ubuntu 22.04/24.04 and Debian 12." >&2
    exit 1
    ;;
esac

export DEBIAN_FRONTEND=noninteractive
apt-get update -y >/dev/null
apt-get install -y ca-certificates curl tar gzip >/dev/null

if [[ "$REF" == v* ]]; then
  URL="https://github.com/${REPO}/archive/refs/tags/${REF}.tar.gz"
else
  URL="https://github.com/${REPO}/archive/refs/heads/${REF}.tar.gz"
fi

echo "============================================================"
echo " ${PROJECT} Easy Installer"
echo " Source: ${REPO}@${REF}"
echo "============================================================"

curl -fL --retry 5 --connect-timeout 10 "$URL" -o "$TMP/source.tar.gz"
mkdir -p "$TMP/src"
tar -xzf "$TMP/source.tar.gz" -C "$TMP/src" --strip-components=1

chmod +x "$TMP/src/scripts/manage.sh"
exec bash "$TMP/src/scripts/manage.sh" install --source "$TMP/src" "$@"
