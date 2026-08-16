#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

ROOT="${1:-/opt/ov-panel}"
[[ -d "$ROOT" ]] || { echo "panel source not found: $ROOT" >&2; exit 1; }
STAMP="$(date -u +%Y%m%d-%H%M%S)"
OUT="/root/ov-pvnetwork-production-export-$STAMP"
STAGE="$OUT/stage"
mkdir -p "$STAGE/panel" "$STAGE/system"

# Copy source while excluding runtime state, credentials, build caches and user material.
rsync -a \
  --exclude='.git/' \
  --exclude='.env' --exclude='.env.*' \
  --exclude='.venv/' --exclude='venv/' \
  --exclude='node_modules/' --exclude='frontend/node_modules/' \
  --exclude='frontend/dist/' \
  --exclude='backups/' --exclude='data/' \
  --exclude='*.db' --exclude='*.sqlite*' \
  --exclude='*.log' --exclude='*.pid' --exclude='*.sock' \
  --exclude='*.ovpn' --exclude='*.key' --exclude='*.pem' --exclude='*.p12' --exclude='*.pfx' --exclude='*.crt' \
  --exclude='*.msi' --exclude='*.apk' --exclude='*.dmg' \
  "$ROOT/" "$STAGE/panel/"

for f in \
  /etc/systemd/system/ov-panel.service \
  /etc/systemd/system/ov-node-user-reconcile.service \
  /etc/systemd/system/ov-node-user-reconcile.timer \
  /etc/systemd/system/ov-production-healthcheck.service \
  /etc/systemd/system/ov-production-healthcheck.timer \
  /usr/local/sbin/ov-node-user-reconcile.py \
  /usr/local/sbin/ov-production-healthcheck \
  /usr/local/sbin/ov-sub-push-sender.py
do
  [[ -f "$f" ]] && cp -a "$f" "$STAGE/system/$(basename "$f")"
done

# Conservative first-pass secret scan. Any hit must be manually reviewed.
SCAN="$OUT/secret-scan.txt"
grep -RInE --binary-files=without-match \
  '(BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY|ADMIN_PASSWORD[[:space:]]*=|JWT_SECRET_KEY[[:space:]]*=|API_KEY[[:space:]]*=[[:space:]]*[^$<{[:space:]])' \
  "$STAGE" > "$SCAN" || true

python3 - "$STAGE" "$OUT/manifest.json" <<'PY'
from pathlib import Path
import hashlib
import json
import sys

root = Path(sys.argv[1])
entries = []
for path in sorted(p for p in root.rglob('*') if p.is_file()):
    content = path.read_bytes()
    entries.append({
        'path': str(path.relative_to(root)),
        'size': len(content),
        'sha256': hashlib.sha256(content).hexdigest(),
    })

Path(sys.argv[2]).write_text(
    json.dumps({'files': entries}, indent=2) + '\n',
    encoding='utf-8',
)
PY

tar -C "$STAGE" -czf "$OUT/ov-pvnetwork-production-source-$STAMP.tar.gz" .
sha256sum "$OUT/ov-pvnetwork-production-source-$STAMP.tar.gz" > "$OUT/SHA256SUMS"
rm -rf "$STAGE"

echo "EXPORT_DIR=$OUT"
echo "ARCHIVE=$OUT/ov-pvnetwork-production-source-$STAMP.tar.gz"
echo "SECRET_SCAN=$SCAN"
if [[ -s "$SCAN" ]]; then
  echo 'SECRET_SCAN=REVIEW_REQUIRED'
else
  echo 'SECRET_SCAN=PASS'
fi
