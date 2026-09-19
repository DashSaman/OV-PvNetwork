#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
AUTH_SCRIPT="$ROOT/scripts/pvnetwork-router-auth"
PY="${PYTHON:-python3}"
TMP="$(mktemp -d /tmp/pvn029-handshake.XXXXXX)"
NS="pvn029-$RANDOM-$$"
PIDS=()

cleanup() {
  for pid in "${PIDS[@]:-}"; do kill "$pid" 2>/dev/null || true; done
  wait 2>/dev/null || true
  ip netns del "$NS" >/dev/null 2>&1 || true
  rm -rf "$TMP"
}
trap cleanup EXIT

command -v openvpn >/dev/null
command -v openssl >/dev/null
command -v ip >/dev/null
ip netns add "$NS"
ip netns exec "$NS" ip link set lo up

free_port() {
  python3 - <<'PY'
import socket
s=socket.socket(); s.bind(('127.0.0.1',0)); print(s.getsockname()[1]); s.close()
PY
}

NORMAL_PORT="$(free_port)"
ROUTER_PORT="$(free_port)"
while [[ "$ROUTER_PORT" == "$NORMAL_PORT" ]]; do ROUTER_PORT="$(free_port)"; done

cd "$TMP"
openssl genrsa -out ca.key 2048 >/dev/null 2>&1
openssl req -x509 -new -key ca.key -sha256 -days 2 -subj '/CN=PVN-Test-CA' -out ca.crt >/dev/null 2>&1
make_cert() {
  local name="$1" eku="$2"
  openssl genrsa -out "$name.key" 2048 >/dev/null 2>&1
  openssl req -new -key "$name.key" -subj "/CN=$name" -out "$name.csr" >/dev/null 2>&1
  cat >"$name.ext" <<EOF
basicConstraints=CA:FALSE
keyUsage=digitalSignature,keyEncipherment
extendedKeyUsage=$eku
subjectKeyIdentifier=hash
authorityKeyIdentifier=keyid,issuer
EOF
  openssl x509 -req -in "$name.csr" -CA ca.crt -CAkey ca.key -CAcreateserial \
    -out "$name.crt" -days 2 -sha256 -extfile "$name.ext" >/dev/null 2>&1
}

make_cert server serverAuth
make_cert client1 clientAuth
make_cert client2 clientAuth
openvpn --genkey secret ta.key >/dev/null 2>&1

VERIFIER="$(PYTHONPATH="$ROOT" "$PY" - <<'PY'
from backend.router_openvpn.credentials import hash_router_password
print(hash_router_password('router-test-password'))
PY
)"
printf 'router_1\tclient1\t1\t%s\n' "$VERIFIER" >credentials.tsv
chmod 600 credentials.tsv

cat >normal-server.conf <<EOF
local 127.0.0.1
port $NORMAL_PORT
proto tcp-server
mode server
dev tun0
topology subnet
server 10.250.0.0 255.255.255.0
tls-server
ca $TMP/ca.crt
cert $TMP/server.crt
key $TMP/server.key
dh none
auth SHA256
data-ciphers AES-256-GCM:AES-256-CBC
ifconfig-noexec
route-noexec
verb 3
EOF

cat >router-server.conf <<EOF
local 127.0.0.1
port $ROUTER_PORT
proto tcp-server
mode server
dev tun1
topology subnet
server 10.251.0.0 255.255.255.0
tls-server
ca $TMP/ca.crt
cert $TMP/server.crt
key $TMP/server.key
dh none
auth SHA256
data-ciphers AES-256-CBC
data-ciphers-fallback AES-256-CBC
tls-auth $TMP/ta.key 0
auth-user-pass-verify $AUTH_SCRIPT via-file
setenv PVNETWORK_ROUTER_CREDENTIAL_FILE $TMP/credentials.tsv
verify-client-cert require
script-security 2
ifconfig-noexec
route-noexec
verb 3
EOF
make_client() {
  local name="$1" port="$2" cert="$3" auth_file="${4:-}" tls_auth="${5:-0}"
  cat >"$name.conf" <<EOF
client
dev tun2
proto tcp-client
remote 127.0.0.1 $port
nobind
tls-client
remote-cert-tls server
ca $TMP/ca.crt
cert $TMP/$cert.crt
key $TMP/$cert.key
auth SHA256
connect-retry-max 1
connect-timeout 2
verb 3
EOF
  if [[ "$tls_auth" == 1 ]]; then
    cat >>"$name.conf" <<EOF
cipher AES-256-CBC
data-ciphers AES-256-CBC
tls-auth $TMP/ta.key 1
EOF
  else
    echo 'data-ciphers AES-256-GCM:AES-256-CBC' >>"$name.conf"
  fi
  if [[ -n "$auth_file" ]]; then
    echo "auth-user-pass $TMP/$auth_file" >>"$name.conf"
  fi
}

printf 'router_1\nrouter-test-password\n' >auth-good.txt
printf 'router_1\nwrong-password\n' >auth-wrong.txt
make_client normal-listener "$NORMAL_PORT" client1 '' 0
make_client router-good "$ROUTER_PORT" client1 auth-good.txt 1
make_client wrong-password "$ROUTER_PORT" client1 auth-wrong.txt 1
make_client wrong-cn "$ROUTER_PORT" client2 auth-good.txt 1

ip netns exec "$NS" env PVNETWORK_ROUTER_CREDENTIAL_FILE="$TMP/credentials.tsv" openvpn --config "$TMP/normal-server.conf" >normal-server.log 2>&1 & PIDS+=("$!")
ip netns exec "$NS" env PVNETWORK_ROUTER_CREDENTIAL_FILE="$TMP/credentials.tsv" openvpn --config "$TMP/router-server.conf" >router-server.log 2>&1 & PIDS+=("$!")
sleep 1

if ! kill -0 "${PIDS[0]}" 2>/dev/null; then cat normal-server.log; exit 30; fi
if ! kill -0 "${PIDS[1]}" 2>/dev/null; then cat router-server.log; exit 31; fi

run_client() {
  local name="$1"
  timeout 8 ip netns exec "$NS" openvpn --config "$TMP/$name.conf" >"$name.log" 2>&1 || true
}

run_client normal-listener
run_client router-good
run_client wrong-password
run_client wrong-cn

grep -q 'Initialization Sequence Completed' normal-listener.log || { cat normal-listener.log; exit 40; }
grep -q 'Initialization Sequence Completed' router-good.log || { cat router-good.log; cat router-server.log; exit 41; }
! grep -q 'Initialization Sequence Completed' wrong-password.log || { cat wrong-password.log; exit 42; }
! grep -q 'Initialization Sequence Completed' wrong-cn.log || { cat wrong-cn.log; exit 43; }

printf 'router_1\tclient1\t0\t%s\n' "$VERIFIER" >credentials.tsv
run_client disabled-credential 2>/dev/null || true
# Reuse the good client config under an explicit disabled-credential marker.
cp router-good.conf disabled-credential.conf
timeout 6 ip netns exec "$NS" openvpn --config "$TMP/disabled-credential.conf" >disabled-credential.log 2>&1 || true
! grep -q 'Initialization Sequence Completed' disabled-credential.log || { cat disabled-credential.log; exit 44; }

echo 'REAL_DUAL_AUTH_HANDSHAKE=PASS'
