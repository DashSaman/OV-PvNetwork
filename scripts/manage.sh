#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

PROJECT="OV-PvNetwork"
REPO="DashSaman/OV-PvNetwork"
APP="/opt/ov-panel"
STATE="/etc/ov-pvnetwork"
LIB="/usr/local/lib/ov-pvnetwork"
BACKUPS="/var/backups/ov-pvnetwork"
MANAGER="/usr/local/sbin/ovpv"
SOURCE=""
COMMAND="${1:-help}"
[[ $# -gt 0 ]] && shift || true

while [[ $# -gt 0 ]]; do
  case "$1" in
    --source) SOURCE="$2"; shift 2;;
    *) break;;
  esac
done

say(){ printf '[OV-PvNetwork] %s\n' "$*"; }
fail(){ printf '[OV-PvNetwork] ERROR: %s\n' "$*" >&2; exit 1; }
need_root(){ [[ "${EUID:-$(id -u)}" -eq 0 ]] || fail "run as root"; }

manifest_value(){ python3 - "$1" "${SOURCE:-$LIB/current}" <<'PY'
import json,sys
key,root=sys.argv[1:]
d=json.load(open(root+'/manifest.json'))
cur=d
for part in key.split('.'):
    cur=cur[part]
print(cur)
PY
}

preflight(){
  need_root
  [[ -r /etc/os-release ]] || fail "/etc/os-release missing"
  . /etc/os-release
  case "${ID:-}" in ubuntu|debian) ;; *) fail "supported OS: Ubuntu/Debian";; esac
  local free
  free="$(df -Pk /opt 2>/dev/null | awk 'NR==2{print $4}' || echo 0)"
  [[ "${free:-0}" -ge 1048576 ]] || fail "at least 1 GiB free space is required"
}

install_deps(){
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -y
  apt-get install -y ca-certificates curl git tar gzip rsync python3 python3-venv python3-full build-essential jq openssl nginx
  if ! command -v uv >/dev/null 2>&1; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="/root/.local/bin:$PATH"
  fi
  if ! command -v node >/dev/null 2>&1 || [[ "$(node -p 'Number(process.versions.node.split(`.`)[0])' 2>/dev/null || echo 0)" -lt 20 ]]; then
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
    apt-get install -y nodejs
  fi
}

make_backup(){
  need_root
  local stamp dir
  stamp="$(date -u +%Y%m%d-%H%M%S)"
  dir="$BACKUPS/$stamp"
  mkdir -p "$dir"
  if [[ -d "$APP" ]]; then
    rsync -a --delete-excluded \
      --exclude='.venv/' --exclude='frontend/node_modules/' --exclude='frontend/dist/' \
      --exclude='backups/' "$APP/" "$dir/panel/"
  fi
  cp -a /etc/systemd/system/ov-panel.service "$dir/" 2>/dev/null || true
  cp -a "$STATE" "$dir/state" 2>/dev/null || true
  printf '%s\n' "$dir" > "$STATE/last-backup" 2>/dev/null || true
  echo "$dir"
}

configure_env(){
  local env="$APP/.env"
  [[ -f "$env" ]] && return 0
  cp "$APP/.env.example" "$env"
  local user pass port path sub secret
  user="${OVPV_ADMIN_USERNAME:-admin}"
  pass="${OVPV_ADMIN_PASSWORD:-}"
  port="${OVPV_PANEL_PORT:-19000}"
  path="${OVPV_PANEL_PATH:-panel}"
  sub="${OVPV_SUBSCRIPTION_PATH:-sub}"
  if [[ -z "$pass" && -t 0 ]]; then
    read -r -p 'Admin username [admin]: ' x; user="${x:-$user}"
    read -r -s -p 'Admin password: ' pass; echo
    read -r -p 'Panel port [19000]: ' x; port="${x:-$port}"
    read -r -p 'Panel path [panel]: ' x; path="${x:-$path}"
    read -r -p 'Subscription path [sub]: ' x; sub="${x:-$sub}"
  fi
  [[ -n "$pass" ]] || pass="$(openssl rand -base64 24 | tr -d '\n')"
  secret="$(openssl rand -base64 64 | tr -d '\n')"
  python3 - "$env" "$user" "$pass" "$port" "$path" "$sub" "$secret" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1]); vals={
 'ADMIN_USERNAME':sys.argv[2], 'ADMIN_PASSWORD':sys.argv[3], 'PORT':sys.argv[4],
 'URLPATH':sys.argv[5], 'VITE_URLPATH':sys.argv[5], 'SUBSCRIPTION_PATH':sys.argv[6],
 'JWT_SECRET_KEY':sys.argv[7], 'HOST':'0.0.0.0'}
lines=p.read_text().splitlines(); out=[]; seen=set()
for line in lines:
    key=line.split('=',1)[0].strip() if '=' in line and not line.lstrip().startswith('#') else None
    if key in vals: out.append(f'{key}={vals[key]}'); seen.add(key)
    else: out.append(line)
for k,v in vals.items():
    if k not in seen: out.append(f'{k}={v}')
p.write_text('\n'.join(out).rstrip()+'\n')
PY
  chmod 600 "$env"
  say "generated admin credentials; save them now: username=$user password=$pass"
}

patch_base(){
  python3 - "$APP/main.py" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1]); s=p.read_text(); s=s.replace('reload=True','reload=False'); p.write_text(s)
PY
}

build_panel(){
  cd "$APP"
  export PATH="/root/.local/bin:$PATH"
  uv sync
  cd "$APP/frontend"
  if [[ -f package-lock.json ]]; then npm ci; else npm install; fi
  npm run build
  cd "$APP"
  if [[ -f backend/alembic.ini ]]; then
    .venv/bin/alembic -c backend/alembic.ini upgrade head
  fi
  python3 -m compileall -q backend
}

install_service(){
  cat > /etc/systemd/system/ov-panel.service <<'UNIT'
[Unit]
Description=OV-PvNetwork Panel
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=/opt/ov-panel
Environment=PATH=/root/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
ExecStart=/root/.local/bin/uv run main.py
Restart=always
RestartSec=3
TimeoutStopSec=20
KillMode=mixed

[Install]
WantedBy=multi-user.target
UNIT
  install -m 0755 "$SOURCE/scripts/healthcheck.sh" /usr/local/sbin/ov-pvnetwork-healthcheck
  cat > /etc/systemd/system/ov-pvnetwork-healthcheck.service <<'UNIT'
[Unit]
Description=OV-PvNetwork control-plane health check
After=network-online.target

[Service]
Type=oneshot
ExecStart=/usr/local/sbin/ov-pvnetwork-healthcheck
UNIT
  cat > /etc/systemd/system/ov-pvnetwork-healthcheck.timer <<'UNIT'
[Unit]
Description=OV-PvNetwork periodic health check

[Timer]
OnBootSec=2min
OnUnitInactiveSec=2min
RandomizedDelaySec=10s
Persistent=true

[Install]
WantedBy=timers.target
UNIT
  systemctl daemon-reload
  systemctl enable --now ov-panel.service ov-pvnetwork-healthcheck.timer
}

persist_distribution(){
  mkdir -p "$LIB" "$STATE" "$BACKUPS"
  rm -rf "$LIB/current.new"
  mkdir -p "$LIB/current.new"
  rsync -a --delete "$SOURCE/" "$LIB/current.new/"
  rm -rf "$LIB/current.old"
  [[ -d "$LIB/current" ]] && mv "$LIB/current" "$LIB/current.old"
  mv "$LIB/current.new" "$LIB/current"
  rm -rf "$LIB/current.old"
  install -m 0755 "$LIB/current/scripts/manage.sh" "$MANAGER"
  printf '%s\n' "$(cat "$LIB/current/VERSION")" > "$STATE/version"
  mkdir -p /usr/local/share/ov-pvnetwork/node
  install -m 0755 "$LIB/current/scripts/ov-build-client-profile" /usr/local/share/ov-pvnetwork/node/
  install -m 0755 "$LIB/current/scripts/node_patch.py" /usr/local/share/ov-pvnetwork/node/
}

verify(){
  systemctl is-active --quiet ov-panel.service || return 1
  local port
  port="$(awk -F= '$1=="PORT"{print $2}' "$APP/.env" | tail -1 | tr -d ' \r')"
  [[ -n "$port" ]] || port=19000
  for _ in $(seq 1 30); do
    curl -fsS --connect-timeout 1 --max-time 2 "http://127.0.0.1:${port}/openapi.json" >/dev/null && return 0
    sleep 1
  done
  return 1
}

fresh_install(){
  preflight
  [[ -n "$SOURCE" && -f "$SOURCE/manifest.json" ]] || fail "installer source missing"
  [[ ! -d "$APP" ]] || fail "$APP already exists; use 'ovpv update' or set up a separate test server"
  install_deps
  local panel_tag tmp url
  panel_tag="$(manifest_value base_panel.tag)"
  tmp="$(mktemp -d /tmp/ovpv-panel.XXXXXX)"
  url="https://github.com/primeZdev/ov-panel/archive/refs/tags/${panel_tag}.tar.gz"
  curl -fL --retry 5 "$url" -o "$tmp/panel.tar.gz"
  mkdir -p "$APP"
  tar -xzf "$tmp/panel.tar.gz" -C "$APP" --strip-components=1
  rm -rf "$tmp"
  configure_env
  patch_base
  build_panel
  persist_distribution
  install_service
  verify || fail "panel health verification failed"
  say "installation complete"
  say "run: ovpv status"
}

update_install(){
  need_root
  [[ -d "$APP" ]] || fail "panel is not installed"
  local tmp ref backup
  backup="$(make_backup)"; say "backup: $backup"
  tmp="$(mktemp -d /tmp/ovpv-update.XXXXXX)"
  ref="${OVPV_REF:-main}"
  curl -fL --retry 5 "https://github.com/${REPO}/archive/refs/heads/${ref}.tar.gz" -o "$tmp/src.tar.gz"
  mkdir -p "$tmp/src"; tar -xzf "$tmp/src.tar.gz" -C "$tmp/src" --strip-components=1
  SOURCE="$tmp/src"
  persist_distribution
  patch_base
  build_panel
  systemctl restart ov-panel.service
  if ! verify; then
    say "verification failed; restoring backup"
    restore_backup "$backup"
    rm -rf "$tmp"
    fail "update rolled back"
  fi
  rm -rf "$tmp"
  say "update complete: $(cat "$STATE/version")"
}

restore_backup(){
  local dir="$1"
  [[ -d "$dir/panel" ]] || fail "invalid backup: $dir"
  systemctl stop ov-panel.service || true
  rsync -a --delete "$dir/panel/" "$APP/"
  [[ -f "$dir/ov-panel.service" ]] && cp -a "$dir/ov-panel.service" /etc/systemd/system/ov-panel.service
  systemctl daemon-reload
  systemctl start ov-panel.service
}

status(){
  echo "OV-PvNetwork version: $(cat "$STATE/version" 2>/dev/null || echo unknown)"
  echo "Panel: $(systemctl is-active ov-panel.service 2>/dev/null || true)"
  echo "Health timer: $(systemctl is-active ov-pvnetwork-healthcheck.timer 2>/dev/null || true)"
  [[ -f "$APP/.env" ]] && awk -F= '$1=="PORT"||$1=="URLPATH"||$1=="SUBSCRIPTION_PATH"{print $1"="$2}' "$APP/.env"
}

doctor(){
  status
  echo '-- API --'
  local port
  port="$(awk -F= '$1=="PORT"{print $2}' "$APP/.env" 2>/dev/null | tail -1 | tr -d ' \r')"; port="${port:-19000}"
  curl -sS -o /dev/null -w 'HTTP=%{http_code} TIME=%{time_total}s\n' "http://127.0.0.1:${port}/openapi.json" || true
  echo '-- disk --'; df -h / /opt 2>/dev/null | uniq
  echo '-- timers --'; systemctl list-timers --all --no-pager | grep -E 'ov-pvnetwork|ov-node-user-reconcile|ov-production' || true
}

case "$COMMAND" in
  install) fresh_install;;
  update) update_install;;
  backup) preflight; make_backup;;
  rollback) need_root; dir="${1:-$(cat "$STATE/last-backup" 2>/dev/null)}"; [[ -n "$dir" ]] || fail "no backup selected"; restore_backup "$dir"; verify || fail "restored panel is unhealthy"; say "rollback complete";;
  status) status;;
  doctor) doctor;;
  version) cat "$STATE/version" 2>/dev/null || cat "$LIB/current/VERSION" 2>/dev/null || echo unknown;;
  help|*) cat <<'EOF'
OV-PvNetwork manager
  ovpv status
  ovpv doctor
  ovpv update
  ovpv backup
  ovpv rollback [backup-directory]
  ovpv version
EOF
  ;;
esac
