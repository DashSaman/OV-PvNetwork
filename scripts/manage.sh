#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

REPO="DashSaman/OV-PvNetwork"
APP="/opt/pvnetwork-panel"
STATE="/etc/pvnetwork-panel"
BACKUPS="/var/backups/pvnetwork-panel/lifecycle"
MANAGER="/usr/local/sbin/pvnetwork"
COMMAND="${1:-help}"
[[ $# -gt 0 ]] && shift || true

say(){ printf '[PVNetwork] %s\n' "$*"; }
fail(){ printf '[PVNetwork] ERROR: %s\n' "$*" >&2; exit 1; }
need_root(){ [[ "${EUID:-$(id -u)}" -eq 0 ]] || fail 'run as root'; }
need_install(){ [[ -d "$APP" && -f "$APP/main.py" ]] || fail 'panel is not installed'; }

panel_port(){
  awk -F= '$1=="PORT"{print $2}' "$APP/.env" 2>/dev/null | tail -1 | tr -d ' \r' | sed 's/^$/19000/'
}

current_version(){
  cat "$APP/VERSION" 2>/dev/null || cat "$STATE/version" 2>/dev/null || echo unknown
}

verify(){
  systemctl is-active --quiet pvnetwork-panel.service || return 1
  local port="$(panel_port)"
  for _ in $(seq 1 30); do
    curl -fsS --connect-timeout 1 --max-time 2 "http://127.0.0.1:${port}/openapi.json" >/dev/null && return 0
    sleep 1
  done
  return 1
}
latest_ref(){
  if [[ -n "${PVNETWORK_REF:-}" ]]; then printf '%s\n' "$PVNETWORK_REF"; return; fi
  local tag
  tag="$(curl -fsSL --connect-timeout 5 "https://api.github.com/repos/${REPO}/releases/latest" 2>/dev/null | python3 -c 'import json,sys; print(json.load(sys.stdin).get("tag_name", ""))' 2>/dev/null || true)"
  [[ -n "$tag" ]] && printf '%s\n' "$tag" || printf 'v%s\n' "$(current_version)"
}

fetch_source(){
  local ref="$1" out="$2" url
  if [[ "$ref" == v* ]]; then
    url="https://github.com/${REPO}/archive/refs/tags/${ref}.tar.gz"
  else
    url="https://github.com/${REPO}/archive/refs/heads/${ref}.tar.gz"
  fi
  mkdir -p "$out"
  curl -fL --retry 5 --connect-timeout 10 "$url" -o "$out/source.tar.gz"
  mkdir -p "$out/src"
  tar -xzf "$out/source.tar.gz" -C "$out/src" --strip-components=1
  [[ -f "$out/src/VERSION" && -f "$out/src/main.py" ]] || fail 'downloaded source is incomplete'
}

warn_external_db(){
  local db
  db="$(awk -F= '$1=="DATABASE_URL"{sub(/^DATABASE_URL=/,"");print}' "$APP/.env" 2>/dev/null | tail -1)"
  if [[ "$db" == postgresql* || "$db" == postgres* ]]; then
    say 'external PostgreSQL detected: keep a database-native backup before upgrades.'
  fi
}
make_backup(){
  need_root; need_install
  local stamp dir
  stamp="$(date -u +%Y%m%d-%H%M%S)"
  dir="$BACKUPS/$stamp"
  mkdir -p "$dir/panel" "$STATE" "$BACKUPS"
  rsync -a \
    --exclude='.venv/' \
    --exclude='frontend/node_modules/' \
    --exclude='frontend/dist/' \
    --exclude='backups/' \
    "$APP/" "$dir/panel/"
  cp -a /etc/systemd/system/pvnetwork-panel.service "$dir/" 2>/dev/null || true
  printf '%s\n' "$dir" > "$STATE/last-backup"
  say "backup created: $dir" >&2
  printf '%s\n' "$dir"
}

build_panel(){
  cd "$APP"
  export PATH="/root/.local/bin:$PATH"
  command -v uv >/dev/null 2>&1 || fail 'uv is not installed'
  command -v node >/dev/null 2>&1 || fail 'node is not installed'
  uv sync
  (cd frontend && npm ci && npm run build)
  .venv/bin/python -m compileall -q backend
  [[ -f backend/alembic.ini ]] && .venv/bin/alembic -c backend/alembic.ini upgrade head
}
sync_source(){
  local src="$1"
  rsync -a --delete \
    --exclude='.git/' \
    --exclude='.env' \
    --exclude='data/' \
    --exclude='.venv/' \
    --exclude='frontend/node_modules/' \
    --exclude='frontend/dist/' \
    --exclude='backups/' \
    "$src/" "$APP/"
  "$APP/scripts/install-runtime-tools.sh"
  mkdir -p "$STATE"
  printf '%s\n' "$(cat "$APP/VERSION")" > "$STATE/version"
}

update_install(){
  need_root; need_install; warn_external_db
  local backup tmp ref
  backup="$(make_backup | tail -1)"
  tmp="$(mktemp -d /tmp/pvnetwork-update.XXXXXX)"
  trap 'rm -rf "$tmp"' RETURN
  ref="$(latest_ref)"
  say "target release: $ref"
  fetch_source "$ref" "$tmp"
  sync_source "$tmp/src"
  build_panel
  systemctl restart pvnetwork-panel.service
  if ! verify; then
    say 'verification failed; restoring pre-update backup'
    restore_backup "$backup"
    fail 'update rolled back'
  fi
  say "update complete: $(current_version)"
}
restore_backup(){
  local dir="$1"
  [[ -d "$dir/panel" ]] || fail "invalid backup: $dir"
  systemctl stop pvnetwork-panel.service || true
  rsync -a --delete \
    --exclude='.venv/' \
    --exclude='frontend/node_modules/' \
    --exclude='frontend/dist/' \
    "$dir/panel/" "$APP/"
  [[ -f "$dir/pvnetwork-panel.service" ]] && cp -a "$dir/pvnetwork-panel.service" /etc/systemd/system/pvnetwork-panel.service
  systemctl daemon-reload
  build_panel
  systemctl start pvnetwork-panel.service
  verify || fail 'restored panel is unhealthy'
  "$APP/scripts/install-runtime-tools.sh"
  mkdir -p "$STATE"
  printf '%s\n' "$(cat "$APP/VERSION" 2>/dev/null || echo unknown)" > "$STATE/version"
}

status_cmd(){
  echo "PVNetwork version: $(current_version)"
  echo "Panel: $(systemctl is-active pvnetwork-panel.service 2>/dev/null || true)"
  if [[ -f "$APP/.env" ]]; then
    awk -F= '$1=="PORT"||$1=="URLPATH"||$1=="SUBSCRIPTION_PATH"{print $1"="$2}' "$APP/.env"
  fi
}
doctor_cmd(){
  need_install
  status_cmd
  echo '-- API --'
  local port="$(panel_port)"
  curl -sS -o /dev/null -w 'HTTP=%{http_code} TIME=%{time_total}s\n' "http://127.0.0.1:${port}/openapi.json" || true
  echo '-- disk --'
  df -h / /opt 2>/dev/null | uniq
  echo '-- service --'
  systemctl --no-pager --full status pvnetwork-panel.service 2>/dev/null | sed -n '1,12p' || true
}

case "$COMMAND" in
  status) status_cmd ;;
  doctor) doctor_cmd ;;
  version) current_version ;;
  backup) make_backup >/dev/null ;;
  update) update_install ;;
  rollback)
    need_root; need_install
    dir="${1:-$(cat "$STATE/last-backup" 2>/dev/null || true)}"
    [[ -n "$dir" ]] || fail 'no backup selected'
    restore_backup "$dir"
    say "rollback complete: $(current_version)"
    ;;
  help|*) cat <<'EOF'
PVNetwork manager
  pvnetwork status
  pvnetwork doctor
  pvnetwork version
  pvnetwork backup
  pvnetwork update
  pvnetwork rollback [backup-directory]

Set PVNETWORK_REF=v1.1.0 (or a branch name) to target a specific update source.
EOF
  ;;
esac
