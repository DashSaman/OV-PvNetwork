#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

REPO="DashSaman/OV-PvNetwork"
TAG="${PVNETWORK_VERSION:-v1.0.0}"
[[ "$TAG" == v* ]] || TAG="v$TAG"
ASSET="pvnetwork-panel-${TAG}.tar.gz"
TMP="$(mktemp -d /tmp/pvnetwork-install.XXXXXX)"
trap 'rm -rf "$TMP"' EXIT

[[ ${EUID:-$(id -u)} -eq 0 ]] || { echo '[PVNetwork] run as root' >&2; exit 1; }

curl -fL --retry 5 --connect-timeout 10 \
  "https://github.com/${REPO}/releases/download/${TAG}/${ASSET}" \
  -o "$TMP/$ASSET"
curl -fL --retry 5 --connect-timeout 10 \
  "https://github.com/${REPO}/releases/download/${TAG}/SHA256SUMS" \
  -o "$TMP/SHA256SUMS"

(cd "$TMP" && grep " ${ASSET}$" SHA256SUMS | sha256sum -c -)
mkdir -p "$TMP/source"
tar -xzf "$TMP/$ASSET" -C "$TMP/source" --strip-components=1
exec bash "$TMP/source/install-local.sh" "$@"
