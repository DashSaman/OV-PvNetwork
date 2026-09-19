# PVN-029 Router/OpenVPN Compatibility Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an opt-in RouterOS/OpenVPN certificate+password path on a secondary Node listener while leaving the existing certificate-only listener and normal `.ovpn` profiles unchanged.

**Architecture:** Each compatible Node gets an independently managed `pvnetwork-router` OpenVPN instance with its own TCP port, tunnel pool, status file, tls-auth key and root-only credential verifier store. The panel stores only router credential metadata and a password verifier; plaintext router passwords are returned once at create/rotate time and are never persisted centrally. Existing client certificates/Common Names remain the canonical identity so the current session hooks, device limits and user accounting continue to work.

**Tech Stack:** FastAPI, SQLAlchemy/Alembic, PostgreSQL/SQLite test compatibility, OpenVPN 2.6, systemd, Bash/Python Node helpers, React/Vite, Playwright smoke tests.

**Spec:** `docs/superpowers/specs/2026-09-19-router-openvpn-compatibility-design.md`

## Global Constraints

- Target release is exactly `v1.0.9` / `PVN-029`; no unrelated Production-visible feature ships in this patch.
- Main-listener immutability: do not edit normal `server.conf`, normal port/protocol/crypto, normal client template, existing certificate/key material or normal service unit.
- Normal users remain certificate-only and never need username/password.
- Router compatibility is disabled by default per Node and credentials are created only by explicit operator action per user+Node.
- Default Router auth is certificate + password; password-only mode is out of scope.
- Router username must be safe ASCII and <= 27 characters.
- Plaintext router passwords are one-time return values only and must never be stored in the panel database or logs.
- Enabling/disabling the compatibility listener must not restart `openvpn-server@server`.
- Existing device-limit/session hooks continue to use certificate Common Name, not router username.
## Review Focus

- Port/subnet collision: enabling a listener on an occupied port or overlapping tunnel subnet must fail preflight without creating files or firewall rules. Covered in Task 3.
- Credential replay/mismatch: correct password with the wrong client certificate CN must fail. Covered in Task 2 and Task 3.
- Partial Node failure: if systemd start or firewall apply fails, secondary-listener changes must roll back while the normal listener hash/session state remains untouched. Covered in Task 3 and Task 8.
- Stale assignment/state: removing a user's Node assignment or disabling/deleting the user must disable router auth without creating/recreating credentials. Covered in Task 6.
- Old Node capability: Nodes without router-compat API support must report `upgrade_required` and normal OpenVPN actions must continue unaffected. Covered in Task 4 and Task 5.

## File Structure

- `backend/db/models.py` — central metadata models for Node router compatibility and per-user/per-Node router credentials.
- `backend/alembic/versions/<new>_router_openvpn_compatibility.py` — additive schema migration; no changes to existing Node OpenVPN columns.
- `backend/routers/router_openvpn.py` — authenticated panel API for Node compatibility state and per-user credential/profile operations.
- `backend/node/requests.py` — panel-to-Node client methods for the new `/sync/router-openvpn/*` API.
- `scripts/node_patch.py` — Node API endpoints and service/config/credential helper installation for existing upgraded Nodes.
- `scripts/pvnetwork-router-openvpn` — root-only Node helper for preflight, enable, disable, credential set/revoke and profile generation.
- `backend/node/deploy.py` — install the helper/capability on newly deployed Nodes without altering normal listener behavior.
- `backend/routers/users.py` — lifecycle hooks that disable router credentials when the user or assignment is disabled/removed.
- `backend/operations/live_presence.py` — merge secondary status into display presence without double-counting user identity.
- `frontend/src/components/RouterOpenVpnUserModal.jsx` — one-time credential/profile operator flow.
- `frontend/src/components/RouterOpenVpnNodeModal.jsx` — Node preflight and enable/disable flow.
- `frontend/src/components/UserTable.jsx`, `frontend/src/components/NodeTable.jsx`, corresponding pages/lang files — expose the opt-in actions.
- `tests/test_router_openvpn_*.py` plus `frontend/tests/router-openvpn-smoke.mjs` — contract, Node helper, lifecycle and browser gates.
### Task 1: Add additive central metadata schema

**Files:**
- Modify: `backend/db/models.py`
- Create: `backend/alembic/versions/<revision>_router_openvpn_compatibility.py`
- Test: `tests/test_router_openvpn_schema.py`

**Interfaces:**
- Produces: `NodeRouterOpenVpnConfig(node_id, enabled, port, protocol, subnet, capability_version, last_verified_at, last_error)`.
- Produces: `RouterOpenVpnCredential(user_uuid, node_id, router_username, password_hash, enabled, created_at, updated_at, password_changed_at, last_authenticated_at)`.

- [ ] **Step 1: Write the failing schema contract test**

```python
from backend.db.models import NodeRouterOpenVpnConfig, RouterOpenVpnCredential

def test_router_models_are_additive_and_never_store_plaintext_password():
    assert NodeRouterOpenVpnConfig.__tablename__ == "node_router_openvpn"
    assert RouterOpenVpnCredential.__tablename__ == "router_openvpn_credentials"
    columns = {c.name for c in RouterOpenVpnCredential.__table__.columns}
    assert "password_hash" in columns
    assert "password" not in columns
    assert "password_ciphertext" not in columns
    assert {"user_uuid", "node_id"}.issubset(columns)
```

- [ ] **Step 2: Run `python -m unittest tests.test_router_openvpn_schema -v` and verify RED because models/migration do not exist.**
- [ ] **Step 3: Add the two SQLAlchemy models and an additive Alembic migration with FK cascades, unique `(user_uuid,node_id)`, port range check, protocol check `tcp|udp`, and defaults `enabled=false`, `port=1195`, `protocol=tcp`.**
- [ ] **Step 4: Run the focused test plus `alembic upgrade head` against disposable SQLite/PostgreSQL test databases; verify existing `nodes.ovpn_port` is untouched.**
- [ ] **Step 5: Commit `feat: add router OpenVPN metadata schema`.**
### Task 2: Build central one-time router credential service

**Files:**
- Create: `backend/router_openvpn/credentials.py`
- Test: `tests/test_router_openvpn_credentials.py`

**Interfaces:**
- Produces: `generate_router_username(user_uuid: str, node_id: int) -> str`.
- Produces: `hash_router_password(password: str) -> str` and `verify_router_password(password: str, encoded: str) -> bool`.
- Produces: `rotate_router_credential(db, *, user_uuid: str, node_id: int) -> dict` returning only `{router_username, password, enabled}`; DB stores only the verifier.

- [ ] **Step 1: Write RED tests for username safety, password entropy, verifier behavior and one-time storage.**

```python
def test_generated_router_username_is_routeros_safe():
    value = generate_router_username("12345678-1234-5678-1234-567812345678", 42)
    assert 1 <= len(value) <= 27
    assert value.replace("_", "").isalnum()

def test_hash_verifies_without_plaintext_roundtrip():
    encoded = hash_router_password("S3cure-Example-Password")
    assert verify_router_password("S3cure-Example-Password", encoded)
    assert not verify_router_password("wrong", encoded)
    assert "S3cure-Example-Password" not in encoded
```

- [ ] **Step 2: Run `python -m unittest tests.test_router_openvpn_credentials -v`; verify RED.**
- [ ] **Step 3: Implement `hashlib.scrypt` (stdlib, memory-hard) with random 16-byte salt, `n=32768`, `r=8`, `p=1`, URL-safe random 24+ byte plaintext passwords, `hmac.compare_digest`, and deterministic short usernames such as `r_<base32 uuid prefix>_<node_id>` capped at 27 chars. Encode verifier as `scrypt$n$r$p$<salt_b64>$<digest_b64>`.**
- [ ] **Step 4: Persist only `password_hash`; explicitly zero/drop local plaintext references after response construction and ensure no logger call receives password data.**
- [ ] **Step 5: Run focused tests and Bandit on the new module; commit `feat: add one-time router credential service`.**
### Task 3: Implement isolated Node compatibility helper and real dual-auth verifier

**Files:**
- Create: `scripts/pvnetwork-router-openvpn`
- Modify: `scripts/node_patch.py`
- Test: `tests/test_router_openvpn_node_helper.py`
- Test: `tests/test_router_openvpn_handshake.py`

**Interfaces:**
- Node command: `pvnetwork-router-openvpn preflight --port N --subnet CIDR --protocol tcp|udp`.
- Node command: `... enable|disable`, `credential-set --cn CN --username U --verifier HASH`, `credential-revoke --cn CN`, `profile --cn CN`.
- Node API: `/sync/router-openvpn/status`, `/preflight`, `/config`, `/credential`, `/profile/{cn}` authenticated with existing Node API key.

- [ ] **Step 1: Write RED tests proving the helper never opens or rewrites `/etc/openvpn/server/server.conf`, rejects occupied port/subnet, and requires CN+password together.**
- [ ] **Step 2: Add a Node-side verifier script that receives OpenVPN auth via a temporary auth file, reads `username` and `password`, maps username to an expected CN/verifier record, compares the password verifier in constant time, and rejects when `common_name != expected_cn`.**
- [ ] **Step 3: Generate `/etc/openvpn/server/pvnetwork-router.conf` only for the secondary instance with directives equivalent to:**

```conf
port 1195
proto tcp-server
dev tun-router
server 10.9.0.0 255.255.255.0
auth SHA256
data-ciphers AES-256-CBC
data-ciphers-fallback AES-256-CBC
tls-auth /etc/openvpn/server/pvnetwork-router-ta.key 0
auth-user-pass-verify /usr/local/libexec/pvnetwork-router-auth via-file
verify-client-cert require
script-security 2
client-connect /usr/local/libexec/ov-session-connect
client-disconnect /usr/local/libexec/ov-session-disconnect
status /var/log/openvpn-router-status.log 10
```

- [ ] **Step 4: Reuse existing CA/server cert/client cert chain read-only; create a secondary root-only `ta.key`, credential store and profile template; never touch `tc.key`, `client-common.txt` or normal PKI files.**
- [ ] **Step 5: Add preflight snapshots/hashes and rollback: on any config parse/systemd/firewall failure, stop only `openvpn-server@pvnetwork-router`, remove/restore secondary files/rules, and assert normal listener hash is unchanged.**
- [ ] **Step 6: Add an isolated integration test namespace/container that starts both OpenVPN instances and proves: normal certificate-only handshake still succeeds; secondary correct cert+password succeeds; wrong password fails; correct password with wrong CN fails; disabled credential fails.**
- [ ] **Step 7: Run `bash -n scripts/pvnetwork-router-openvpn`, Node helper unit tests and isolated handshake test; capture normal config/profile SHA256 before/after and assert equality.**
- [ ] **Step 8: Commit `feat: add isolated router OpenVPN node helper`.**

### Task 4: Wire capability into Node deployment and panel-to-Node client

**Files:**
- Modify: `backend/node/deploy.py`
- Modify: `backend/node/requests.py`
- Modify: `scripts/install-runtime-tools.sh`
- Test: `tests/test_router_openvpn_node_contract.py`

**Interfaces:**
- `NodeRequests.router_openvpn_status() -> dict`.
- `NodeRequests.router_openvpn_preflight(port:int, protocol:str, subnet:str) -> dict`.
- `NodeRequests.router_openvpn_config(*, enabled:bool, port:int, protocol:str, subnet:str) -> dict`.
- `NodeRequests.router_openvpn_set_credential(cn:str, username:str, verifier:str, enabled:bool) -> dict`.
- `NodeRequests.router_openvpn_profile(cn:str) -> Response | None`.

- [ ] **Step 1: Write RED contract tests that mock old Nodes returning 404 and require the client to normalize that to `{capable: false, upgrade_required: true}` rather than failing normal Node health.**
- [ ] **Step 2: Extend `NodeRequests` with only the new router endpoints and strict timeouts; do not alter existing `check_node`, `create_user`, `download_ovpn_client` semantics.**
- [ ] **Step 3: Update fresh Node deployment to install the helper/verifier capability files but leave the secondary service disabled and port unopened.**
- [ ] **Step 4: Extend the existing pinned-SSH fleet upgrade payload so explicit Node upgrades install the capability idempotently; no automatic hidden upgrade from Router UI.**
- [ ] **Step 5: Run focused tests, shell syntax and current Node deployment regression suite; commit `feat: ship router OpenVPN node capability`.**
### Task 5: Add authenticated panel API for Node compatibility state

**Files:**
- Create: `backend/routers/router_openvpn.py`
- Modify: `backend/app.py`
- Test: `tests/test_router_openvpn_api.py`

**Interfaces:**
- `GET /api/router-openvpn/nodes/{node_id}` returns configured/capable/healthy/upgrade_required plus port/protocol/subnet.
- `POST /api/router-openvpn/nodes/{node_id}/preflight` validates requested settings without mutation.
- `PUT /api/router-openvpn/nodes/{node_id}` enables/disables after successful preflight and updates metadata only after Node confirmation.

- [ ] **Step 1: Write RED API tests for main-admin/admin visibility, missing Node, old capability, occupied-port preflight, idempotent enable, idempotent disable and Node failure rollback.**
- [ ] **Step 2: Implement role/Node visibility using the same ownership rules as existing Node/User routes; never return Node API keys or SSH material.**
- [ ] **Step 3: On enable, call preflight first, then Node config, then re-read status; commit DB metadata only if Node reports healthy. On failure, keep prior DB state and surface a 409/502 with safe detail.**
- [ ] **Step 4: On disable, stop only the secondary instance and revoke its firewall opening; keep credential metadata disabled for audit/rotation history.**
- [ ] **Step 5: Register the router under `/api`, run focused API tests plus OpenAPI/production-doc regression tests, then commit `feat: add router OpenVPN node API`.**

### Task 6: Add per-user credential/profile API and lifecycle enforcement

**Files:**
- Modify: `backend/routers/router_openvpn.py`
- Modify: `backend/routers/users.py`
- Modify: `backend/node/task.py`
- Test: `tests/test_router_openvpn_user_lifecycle.py`

**Interfaces:**
- `GET /api/router-openvpn/users/{uuid}/nodes/{node_id}` returns metadata only; never returns old plaintext password.
- `POST /api/router-openvpn/users/{uuid}/nodes/{node_id}/credential` creates/rotates and returns one-time `{username,password}`.
- `PUT .../credential/status` enables/disables an existing credential.
- `GET .../profile` downloads the secondary Router-compatible `.ovpn` only when Node capability/listener/assignment/credential are valid.
- [ ] **Step 1: Write RED tests requiring active user, explicit Node assignment, healthy compatibility listener and matching client CN before credential creation/profile download.**
- [ ] **Step 2: Implement create/rotate as a transaction: generate central verifier+one-time plaintext, push verifier+CN to Node, persist central verifier metadata only after Node success, then return plaintext exactly once.**
- [ ] **Step 3: Ensure subsequent `GET status` has `password_available=false` and no endpoint can reveal the old plaintext; rotation is the only recovery path.**
- [ ] **Step 4: In user disable/delete and assignment-removal flows, disable/revoke the relevant Node router credential after the authoritative DB decision; failures are logged/audited and queued for reconciliation without rolling back the core user lifecycle.**
- [ ] **Step 5: Preserve canonical Common Name `f"{user.name}-{node.name}"`; do not enable `username-as-common-name`; confirm connect/disconnect hooks still enforce current device limits.**
- [ ] **Step 6: Run user lifecycle, assignment, device-limit and normal `.ovpn` download regression tests; commit `feat: add router OpenVPN user credentials`.**

### Task 7: Merge secondary listener into observability without double counting

**Files:**
- Modify: `scripts/node_patch.py`
- Modify: `backend/operations/live_presence.py`
- Modify: `backend/node/health.py`
- Test: `tests/test_router_openvpn_presence.py`

**Interfaces:**
- Node status payload adds `router_openvpn: {capable, enabled, healthy, online_clients, port, protocol}`.
- Global presence continues to expose unique PVNetwork user identity; raw per-listener counts remain available for Node diagnostics.

- [ ] **Step 1: Write RED tests with the same CN connected to normal and router listeners and assert global unique online total increments once, while Node raw metrics expose both sessions.**
- [ ] **Step 2: Parse `/var/log/openvpn-router-status.log` independently and merge CNs into the existing display-only presence set before UUID dedupe.**
- [ ] **Step 3: Keep `active_sessions` enforcement semantics untouched; this task must not synthesize or delete enforcement rows from status reads.**
- [ ] **Step 4: Run online-truth regression tests from v1.0.6/v1.0.7 plus the new secondary-listener cases; commit `feat: observe router OpenVPN sessions safely`.**
### Task 8: Add Node and User Router/MikroTik UI flows

**Files:**
- Create: `frontend/src/components/RouterOpenVpnNodeModal.jsx`
- Create: `frontend/src/components/RouterOpenVpnUserModal.jsx`
- Modify: `frontend/src/pages/NodeManagement.jsx`
- Modify: `frontend/src/pages/UserManagement.jsx`
- Modify: `frontend/src/components/NodeTable.jsx`
- Modify: `frontend/src/components/UserTable.jsx`
- Modify: `frontend/src/lang/en.json`, `frontend/src/lang/fa.json`
- Test: `frontend/tests/router-openvpn-smoke.mjs`

**Interfaces:**
- Node action opens preflight/status modal; no mutation until explicit Enable/Disable click.
- User action appears only when user is assigned to a Node whose secondary listener is healthy.
- Credential modal shows generated username/password once, provides profile download and RouterOS copy text, then forgets password on close/reload.

- [ ] **Step 1: Write browser RED fixtures for capable/healthy Node, old Node `upgrade_required`, credential create/rotate/revoke, one-time password disappearance after reload, EN/FA and 390/1440 px.**
- [ ] **Step 2: Implement Node modal fields `enabled`, `port`, `protocol`, `subnet` with preflight result; disable Enable while preflight is stale/failing.**
- [ ] **Step 3: Implement User modal with Node selector, credential status, Generate/Rotate, Disable/Revoke, Download Router Profile and copyable RouterOS import text.**

```text
/interface/ovpn-client/import-ovpn-configuration file-name=<profile>.ovpn ovpn-user=<generated-user> ovpn-password=<one-time-password> skip-cert-import=no
```

- [ ] **Step 4: Add explicit copy: `Normal OpenVPN remains certificate-only and does not need these credentials.` / Persian equivalent. Never add username/password fields to normal Download OpenVPN.**
- [ ] **Step 5: Run ESLint/build, focused browser smoke and full existing responsive matrix; commit `feat: add Router MikroTik compatibility UI`.**
### Task 9: Release gates, canary Node rollout, documentation and v1.0.9 publication

**Files:**
- Modify: `.github/workflows/ci.yml`
- Modify: `VERSION`, `CHANGELOG.md`, `README.md`, `README.fa.md`, `ROADMAP.md`, `AGENTS.md`
- Create: `docs/RELEASE-NOTES-v1.0.9.md`, `docs/RELEASE-NOTES-v1.0.9.fa.md`
- Create: sanitized EN/FA screenshots under `docs/images/v1.0.9/`

**Interfaces:**
- Release is complete only after exact-head CI, one Production canary Node, normal-listener immutability evidence, PR merge, main CI, tag, GitHub Release artifact/checksum and post-download verification all pass.

- [ ] **Step 1: Add CI gates for router credential/unit/lifecycle tests, `bash -n`, Bandit/pip-audit, normal-listener immutability fixture and the Router browser smoke.**
- [ ] **Step 2: Run the full local release gate: all Python unit/governance tests, compile, shell/JSON/uv-lock, ESLint/build/npm audit, full browser matrix, Router smoke and disposable real OpenVPN dual-auth handshake.**
- [ ] **Step 3: Before Production mutation, create verified panel app + native DB backup and a Node backup containing secondary-target paths/firewall snapshots; record normal `server.conf`, normal template/profile SHA256 and current live-session count.**
- [ ] **Step 4: Upgrade exactly one compatible canary Node capability through the pinned-SSH fleet path; verify the normal listener/service PID/config/profile/session baseline remains unchanged before enabling the secondary listener.**
- [ ] **Step 5: Enable Router Compatibility only on the canary Node using an unused chosen port/subnet; do not restart normal OpenVPN. Test with a non-customer test user/certificate and generated one-time password.**
- [ ] **Step 6: Verify correct dual-auth connects, wrong password fails, wrong CN fails, revoke disconnect/prevents reconnect, device-limit accounting works, normal `.ovpn` still connects, panel/public health=200, HTTP 5xx=0 and relevant logs have no real errors.**
- [ ] **Step 7: If any canary gate fails, disable/remove only the secondary listener and restore its files/firewall snapshot; verify the normal listener never changed; keep PVN-029 `[~]`.**
- [ ] **Step 8: If all gates pass, update bilingual docs/screenshots/release notes, bump VERSION to `1.0.9`, sanitize/secret-scan the public tree, commit and push.**
- [ ] **Step 9: Require exact-head GitHub CI PASS, merge the v1.0.9 PR, require main CI PASS, tag the exact merge commit, publish artifact + SHA256, download from GitHub and re-verify checksum/VERSION/private-file exclusions.**
- [ ] **Step 10: Record Production evidence and release identifiers in `AGENTS.md`, mark `PVN-029 [x]`, then open `v1.0.10 / PVN-030` as the next task; sync governance-only ledger to Production without service restart.**

## Execution Order

Tasks 1→2 establish central invariants; Task 3 proves the isolated listener works before panel orchestration exists. Tasks 4→7 wire deployment/API/lifecycle/observability. Task 8 adds UI only after backend contracts are stable. Task 9 is the serialized release/canary/Production path; no Production mutation occurs earlier.
