#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="${1:-/opt/ov-panel}"
[[ -d "$ROOT" ]] || { echo "missing $ROOT" >&2; exit 1; }
cd "$ROOT"
[[ -x .venv/bin/python3 ]] && .venv/bin/python3 -m compileall -q backend
if [[ -d frontend && -f frontend/package.json ]]; then
  cd frontend
  npm run build >/dev/null
  cd ..
fi
if systemctl is-active --quiet ov-panel.service; then
  port="$(awk -F= '$1=="PORT"{print $2}' .env | tail -1 | tr -d ' \r')"; port="${port:-19000}"
  curl -fsS --connect-timeout 2 --max-time 5 "http://127.0.0.1:${port}/openapi.json" >/dev/null
fi
echo VERIFY=PASS
