#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

APP="/opt/pvnetwork-panel"
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

fail(){ printf '[PVNetwork] ERROR: %s\n' "$*" >&2; exit 1; }
[[ ${EUID:-$(id -u)} -eq 0 ]] || fail "run as root"
[[ ! -e "$APP" || -z "$(ls -A "$APP" 2>/dev/null || true)" ]] || fail "/opt/pvnetwork-panel already exists; this installer is for a fresh server"

. /etc/os-release
case "${ID:-}:${VERSION_ID:-}" in
  ubuntu:22.04|ubuntu:24.04|debian:12) ;;
  *) fail "unsupported OS: ${PRETTY_NAME:-unknown}" ;;
esac

export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y ca-certificates curl rsync python3 python3-venv python3-full build-essential jq openssl

if ! command -v uv >/dev/null 2>&1; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
fi
export PATH="/root/.local/bin:$PATH"
NODE_MAJOR="$(node -p 'Number(process.versions.node.split(`.`)[0])' 2>/dev/null || echo 0)"
if [[ "$NODE_MAJOR" -lt 20 ]]; then
  curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
  apt-get install -y nodejs
fi

mkdir -p "$APP"
rsync -a "$SRC/" "$APP/"
mkdir -p "$APP/data"
cd "$APP"

ADMIN_USER="${PVNETWORK_ADMIN_USERNAME:-admin}"
ADMIN_PASS="${PVNETWORK_ADMIN_PASSWORD:-}"
PANEL_PORT="${PVNETWORK_PORT:-19000}"
PANEL_PATH="${PVNETWORK_PATH:-panel}"
SERVER_IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
PUBLIC_URL="${PVNETWORK_PUBLIC_URL:-http://${SERVER_IP:-127.0.0.1}:${PANEL_PORT}}"

if [[ -z "$ADMIN_PASS" && -t 0 ]]; then
  read -r -p "Admin username [admin]: " input
  ADMIN_USER="${input:-admin}"
  read -r -s -p "Admin password (leave empty to generate): " ADMIN_PASS; echo
  read -r -p "Public base URL [${PUBLIC_URL}]: " input
  PUBLIC_URL="${input:-$PUBLIC_URL}"
fi
[[ -n "$ADMIN_PASS" ]] || ADMIN_PASS="$(openssl rand -base64 24 | tr -d '\n')"
JWT_SECRET="$(openssl rand -hex 48)"
MIRZA_KEY="$(openssl rand -hex 32)"

cat > "$APP/.env" <<ENV
ADMIN_USERNAME=${ADMIN_USER}
ADMIN_PASSWORD=${ADMIN_PASS}
URLPATH=${PANEL_PATH}
VITE_URLPATH=${PANEL_PATH}
HOST=0.0.0.0
PORT=${PANEL_PORT}
DEBUG=WARNING
DOC=false
JWT_SECRET_KEY=${JWT_SECRET}
MIRZA_API_KEY=${MIRZA_KEY}
DATABASE_URL=${PVNETWORK_DATABASE_URL:-}
JWT_ACCESS_TOKEN_EXPIRES=86400
SUBSCRIPTION_URL_PREFIX=${PUBLIC_URL%/}
SUBSCRIPTION_PATH=sub
PVNETWORK_ANYCONNECT_PUBLIC_SERVER=${PVNETWORK_ANYCONNECT_SERVER:-vpn.example.com:9443}
CORS_ORIGINS=${PVNETWORK_CORS_ORIGINS:-${PUBLIC_URL%/}}
ENV
chmod 600 "$APP/.env"

uv sync
(cd frontend && npm ci && npm run build)
.venv/bin/alembic -c backend/alembic.ini upgrade head
"$APP/scripts/install-runtime-tools.sh"

systemctl enable --now pvnetwork-panel.service
for timer in \
  pvnetwork-panel-monitor.timer \
  pvnetwork-panel-smoke.timer \
  pvnetwork-panel-user-notifier.timer \
  pvnetwork-panel-healthcheck.timer \
  pvnetwork-usage-sync.timer \
  pvnetwork-bandwidth-reconcile.timer \
  pvnetwork-sub-push.timer
do
  systemctl enable --now "$timer"
done
if awk -F= '$1=="DATABASE_URL" && $2 ~ /^postgres/{found=1} END{exit !found}' "$APP/.env"; then
  systemctl enable --now pvnetwork-panel-backup.timer
fi

for _ in $(seq 1 30); do
  if curl -fsS --connect-timeout 1 --max-time 2 "http://127.0.0.1:${PANEL_PORT}/openapi.json" >/dev/null; then
    break
  fi
  sleep 1
done
curl -fsS "http://127.0.0.1:${PANEL_PORT}/openapi.json" >/dev/null || fail "local API health check failed"
echo '[PVNetwork] installation verified.'
echo "[PVNetwork] panel: ${PUBLIC_URL%/}/${PANEL_PATH}"
echo "[PVNetwork] admin username: ${ADMIN_USER}"
echo "[PVNetwork] admin password: ${ADMIN_PASS}"
echo '[PVNetwork] save the credentials now; the local .env file is mode 600.'
echo '[PVNetwork] add VPN nodes from Node Management using the automatic SSH deploy workflow.'
