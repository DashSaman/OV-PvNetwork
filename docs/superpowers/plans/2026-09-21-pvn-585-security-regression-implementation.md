# PVN-585 / v1.0.14 Security Regression Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship v1.0.14 as a security-regression release that turns the current trust boundaries into executable tests, fixes only reproduced vulnerabilities, and preserves Production VPN/Node isolation.

**Architecture:** Keep authentication and routing interfaces stable. Add focused tests by security boundary, extract only security primitives proven to be duplicated or inconsistent, and add a read-only Production probe. Stateful adversarial tests run only against isolated test databases/canary; Production gets non-destructive verification.

**Tech Stack:** Python 3.12, FastAPI/Starlette, SQLAlchemy, PyJWT, unittest, Playwright/Chromium, React/Vite, Nginx, systemd, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-21-pvn-585-security-regression-design.md`

## Global Constraints

- Do not add SSO, passkeys, LDAP/RADIUS, new RBAC models, new roles, or unrelated UX.
- Every suspected vulnerability follows reproduce → minimize → fix → regression-test; static suspicion alone is not a finding.
- State-changing adversarial tests use an isolated test DB or validated canary, never live customer state.
- Production probes are non-destructive: health, 401/403, headers, CORS, docs exposure, rate-limit sanity, and final smoke only.
- No test may mutate real users, nodes, credentials, subscriptions, firewall rules, OpenVPN config, Router listener config, or live sessions.
- Only `pvnetwork-panel.service` may restart when required; Node and normal OpenVPN are rollout isolation invariants.
- No confirmed Critical/High finding within approved scope may remain unfixed at release time.
## Review Focus

1. Multiple-hop or malformed `X-Forwarded-For`: trusted loopback proxy must use the appended final address; a direct non-loopback peer must ignore XFF. Task 1 pins both cases.
2. Scoped API token carrying `settings:write`: it must never become an interactive main administrator or reach TOTP/token/panel-credential administration. Task 3 pins this.
3. Delegated admin disabled after JWT issuance: the previously valid JWT must immediately fail authorization. Task 2 pins this.
4. Scope classification ambiguity: `/users`, `/nodes`/`/fleet`, `/audit`, and default settings paths must require the intended exact area/read-write scope, including look-alike paths. Task 3 pins this.
5. Browser-origin and script payloads: unconfigured origins must not receive credentialed CORS headers, and user strings must render as text without script execution. Task 5 pins this.

## File Structure

- Create `backend/auth/authorization.py`: shared authorization predicates for interactive main-admin-only operations.
- Create `tests/test_security_proxy_ip.py`: reverse-proxy/IP trust and allowlist lockout regressions.
- Create `tests/test_security_auth_regression.py`: JWT, delegated-admin lifecycle, API-token identity and privileged-action regressions.
- Create `tests/test_security_scope_regression.py`: API-token prefix/expiry/revocation and route-scope matrix.
- Create `tests/test_security_input_regression.py`: IDOR-style identifier, SQL-injection payload, route-redaction and sensitive output tests.
- Create `frontend/tests/security-regression-smoke.mjs`: browser XSS/CORS credential-transport posture checks using mocked data only.
- Create `scripts/pvnetwork-security-readonly-probe.py`: credential-free, non-mutating Production security probe.
- Modify `backend/security_middleware.py`, `backend/routers/security.py`, `backend/routers/panel_settings.py`, `backend/routers/backups.py` only when reproduced tests require shared primitives.
- Modify `.github/workflows/ci.yml` to make the security regression suite an explicit release gate.
- Update version/release metadata and bilingual release notes for v1.0.14.

---
### Task 1: Canonical reverse-proxy client IP and allowlist self-lockout guard

**Files:**
- Create: `tests/test_security_proxy_ip.py`
- Modify: `backend/security_middleware.py`
- Modify: `backend/routers/security.py`

**Interfaces:**
- Produces: `client_ip(request) -> str` in `backend.security_middleware` as the single client-IP derivation used by middleware and Security Settings.
- Consumes: Starlette/FastAPI `Request` with `request.client.host` and optional `X-Forwarded-For`.

- [ ] **Step 1: Write the failing regression for the reproduced inconsistency**

```python
class DummyClient:
    host = "127.0.0.1"

class DummyRequest:
    client = DummyClient()
    headers = {"x-forwarded-for": "203.0.113.9, 198.51.100.25"}


def test_allowlist_validation_uses_same_final_forwarded_ip_as_middleware():
    from backend.security_middleware import client_ip
    assert client_ip(DummyRequest()) == "198.51.100.25"
```

Add an async endpoint test that submits an allowlist containing only `198.51.100.25/32` while the request carries the same two-hop XFF and asserts the Security Settings save path accepts it. With current code it must fail because `security.py` reads the first hop.
- [ ] **Step 2: Run the focused tests and capture RED**

Run:
```bash
python3 -m unittest tests.test_security_proxy_ip -v
```
Expected: the endpoint lockout test fails because the router uses the leading XFF value; if import fails because `client_ip` is still private, that is also valid RED for the shared-interface extraction.

- [ ] **Step 3: Make client-IP derivation canonical**

Rename `_client_ip` to `client_ip` without changing its trust model, update `SecurityMiddleware` to call it, and replace the duplicate parser in `backend/routers/security.py`:

```python
from backend.security_middleware import client_ip

# inside put(...)
current_ip = client_ip(request)
included = any(
    ipaddress.ip_address(current_ip) in network
    for network in nets
)
```

Add tests for direct non-loopback peers ignoring spoofed XFF, invalid forwarded values falling back safely, IPv6 loopback, and leading spoof entries not changing the final trusted address.

Also drive `SecurityMiddleware` with the same trusted final IP but two different attacker-controlled leading XFF values. Set a low test-only login/general limit and assert the requests share one bucket and reach 429 rather than bypassing throttling by changing the leading spoof value. Reset `_hits`, `_login_hits`, and `_cache` between cases so the test is deterministic.

- [ ] **Step 4: Run focused tests and full existing security hardening test**

```bash
python3 -m unittest tests.test_security_proxy_ip tests.test_security_hardening -v
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/security_middleware.py backend/routers/security.py tests/test_security_proxy_ip.py
git commit -m "security: unify trusted proxy client IP handling"
```

---
### Task 2: JWT and delegated-admin lifecycle regression coverage

**Files:**
- Create: `tests/test_security_auth_regression.py`
- Modify only if a reproduced failure requires it: `backend/auth/auth.py`

**Interfaces:**
- Consumes: `auth.get_current_user(token: str, db: Session)` and `auth.create_access_token(...)`.
- Produces: executable characterization for token signature, expiry, subject/type, main-admin generation, and delegated-admin active-state enforcement.

- [ ] **Step 1: Add deterministic JWT rejection cases**

```python
def test_expired_admin_jwt_is_rejected(self):
    token = jwt.encode(
        {"sub": "alice", "type": "admin", "exp": 1},
        config.JWT_SECRET_KEY,
        algorithm=auth.ALGORITHM,
    )
    with self.assertRaises(HTTPException) as ctx:
        auth.get_current_user(token=token, db=self.db)
    self.assertEqual(ctx.exception.status_code, 401)
```

Also cover **wrong signature** (a token signed with the wrong secret), missing `sub`, unknown `type`, forged `main_admin` subject, and **stale main-admin generation** (`MAIN_ADMIN_AUTH_GENERATION`). Reuse the existing generation tests where possible rather than duplicating helpers.

- [ ] **Step 2: Add disabled-admin stale-session regression**

Create an isolated SQLite `Admin` row, mint a valid delegated-admin JWT, assert it authenticates while `is_active=True`, flip only that row to `False`, then assert the same already-issued JWT returns 401.
- [ ] **Step 3: Run the auth suite**

```bash
python3 -m unittest \
  tests.test_main_admin_generation \
  tests.test_security_auth_regression -v
```
Expected: existing-safe behavior passes. Any unexpected failure is treated as a reproduced finding; do not weaken the assertion.

- [ ] **Step 4: If and only if a case reproduces a bypass, make the smallest auth fix**

The allowed fix surface is `backend/auth/auth.py`; preserve JWT format and existing login API. For example, delegated-admin JWT validation must continue re-reading the admin row:

```python
admin = crud.get_admin_by_username(db, username)
if not admin or not admin.is_active:
    raise credentials_exception
```

Re-run the failing case first, then the whole Task 2 suite.

- [ ] **Step 5: Commit coverage/fix**

```bash
git add tests/test_security_auth_regression.py backend/auth/auth.py
git commit -m "test: lock authentication security regressions"
```

If `backend/auth/auth.py` did not change, omit it from `git add` and keep the commit test-only.

---

### Task 3: API-token scope boundaries and interactive-main-admin authorization

**Files:**
- Create: `backend/auth/authorization.py`
- Create: `tests/test_security_scope_regression.py`
- Modify: `backend/routers/security.py`
- Modify: `backend/routers/panel_settings.py`
- Modify: `backend/routers/backups.py`
- Modify: `backend/auth/auth.py`
- Modify if path classification tests reproduce a defect: `backend/security_middleware.py`
**Interfaces:**
- Produces: `require_interactive_main_admin(user: dict) -> None` in `backend.auth.authorization`.
- Consumes: `user` dicts from `get_current_user`, including optional `auth_kind="api_token"`.
- Scope middleware must classify exact API area prefixes rather than arbitrary substring matches.

- [ ] **Step 1: Reproduce API-token privilege escalation**

Create an API token carrying `settings:write`, authenticate it through `get_current_user`, and call the Security router's main-admin guard. The test must assert 403 for API-token auth:

```python
def test_api_token_cannot_be_interactive_main_admin(self):
    user = {"username": "owner", "type": "main_admin", "auth_kind": "api_token"}
    with self.assertRaises(HTTPException) as ctx:
        require_interactive_main_admin(user)
    self.assertEqual(ctx.exception.status_code, 403)
```

Before the shared helper is wired into `backend/routers/security.py`, add an endpoint-level test proving `settings:write` cannot create/revoke API tokens, change TOTP, or save Security Settings.

- [ ] **Step 2: Run the focused test and capture RED**

```bash
python3 -m unittest tests.test_security_scope_regression -v
```
Expected: at least the Security-router API-token main-admin test fails on current v1.0.13 behavior.

- [ ] **Step 3: Extract one interactive-main-admin guard and reuse it**

```python
# backend/auth/authorization.py
from fastapi import HTTPException

def require_interactive_main_admin(user: dict) -> None:
    if user.get("type") != "main_admin" or user.get("auth_kind") == "api_token":
        raise HTTPException(403, "Interactive main administrator required")
```

Replace the duplicated guards in Security, Panel Settings, and Backups with this helper while preserving response semantics.
- [ ] **Step 4: Pin token prefix, expiry/revocation, and area/read-write scope matrix**

Cover both supported token prefixes (`pvn_` and legacy `ovp_`) and reject unrelated bearer strings. Add a database-backed case where a token row exists for `badprefix_...`; `get_current_user` must still return 401 because unsupported prefixes must never bypass `ApiScopeMiddleware`. If current auth accepts it, fix the JWT-fallback branch before database lookup:

```python
if not token.startswith(("pvn_", "ovp_")):
    raise credentials_exception
```

Create route cases for:

```python
CASES = [
    ("GET", "/api/users/", "users:read", True),
    ("PUT", "/api/users/demo", "users:read", False),
    ("PUT", "/api/users/demo", "users:write", True),
    ("GET", "/api/nodes/", "nodes:read", True),
    ("POST", "/api/fleet/jobs/demo/retry", "nodes:write", True),
    ("GET", "/api/audit/", "audit:read", True),
    ("GET", "/api/security/", "settings:read", True),
    ("PUT", "/api/security/", "settings:write", True),
]
```

Also assert expired/revoked tokens return 401 before scope evaluation. Add look-alike paths such as `/api/settings/users-report` so substring matching cannot accidentally classify a settings route as `users`.

- [ ] **Step 5: If scope classification RED reproduces, replace substring matching with prefix classification**

Use a small deterministic helper such as:

```python
def api_scope_area(path: str) -> str:
    if path == "/api/users" or path.startswith("/api/users/"):
        return "users"
    if path == "/api/nodes" or path.startswith("/api/nodes/") or path == "/api/fleet" or path.startswith("/api/fleet/"):
        return "nodes"
    if path == "/api/audit" or path.startswith("/api/audit/"):
        return "audit"
    return "settings"
```

- [ ] **Step 6: Run focused suites and commit**

```bash
python3 -m unittest \
  tests.test_security_scope_regression \
  tests.test_panel_settings_api \
  tests.test_security_hardening -v
git add backend/auth/authorization.py backend/routers/security.py backend/routers/panel_settings.py backend/routers/backups.py backend/security_middleware.py tests/test_security_scope_regression.py
git commit -m "security: enforce interactive admin and token scopes"
```

---
### Task 4: Identifier abuse, route protection, SQL-injection and redaction regressions

**Files:**
- Create: `tests/test_security_input_regression.py`
- Modify only if a reproduced failure requires it: affected router/CRUD file.

**Interfaces:**
- Consumes existing isolated SQLite patterns from `tests/test_panel_settings_api.py` and router-level function calls.
- Produces a deterministic matrix proving untrusted identifiers stay bound to exact objects and SQL parameters.

- [ ] **Step 1: Add object/identifier abuse cases**

Pin the existing object-level boundaries that actually exist:

```python
IDENTIFIER_CASES = [
    "../other",
    "..%2Fother",
    "' OR 1=1 --",
    '" OR "1"="1',
    "<script>globalThis.pwned=1</script>",
]
```

Assert invalid backup IDs cannot traverse `BACKUP_ROOT`; panel-settings status tokens cannot be replayed for a different `change_id`; unknown user/node UUIDs never fall through to an adjacent object; Router/OpenVPN credential lookup remains bound to the requested user+node pair.

Add redaction assertions: Security Settings token listings never expose `token_hash` or raw tokens; Router/OpenVPN read APIs never expose Node API keys; panel-settings job status never contains password hashes, JWTs, candidate-env contents, or staging paths.

- [ ] **Step 2: Exercise injection payloads through a public integration path in an isolated DB**

Create users `victim` and `other`, call the Mirza `GET /users/{username}` handler with a valid test API key and payload `victim' OR 1=1 --`, and assert the response is 404/validation failure rather than either stored user. Verify row counts and stored names are unchanged after every payload.
- [ ] **Step 3: Add a static SQL interpolation guard for runtime code**

Parse Python AST for calls to SQLAlchemy `text()` / `_session_text()` and fail on f-strings, `%` formatting, or `.format()` arguments. Literal SQL plus bound parameters remains allowed; dialect-selected constant suffixes such as `FOR UPDATE` are allowed only when no request/user value is concatenated.

```python
def unsafe_sql_arg(node):
    return isinstance(node, ast.JoinedStr) or (
        isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mod)
    ) or (
        isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        and node.func.attr == "format"
    )
```

- [ ] **Step 4: Add protected-route exposure inventory**

Inspect effective FastAPI routes and assert every `/api/*` route is in one of these explicit classes: bearer-authenticated admin API, Mirza-key integration, Node-key sync API, login, or deliberately public health/status route. The test must fail when a new API route has no recognized protection boundary.

- [ ] **Step 5: Run and fix only reproduced failures**

```bash
python3 -m unittest tests.test_security_input_regression -v
```

For a real failure, patch only the affected query/route using SQLAlchemy bound parameters or the existing auth dependency. Never broaden a public allowlist to make the test pass.

- [ ] **Step 6: Commit**

```bash
git add tests/test_security_input_regression.py backend/routers backend/db
git commit -m "test: cover identifier and SQL security boundaries"
```

---

### Task 5: CORS, CSRF posture, browser XSS, and credential transport

**Files:**
- Create: `frontend/tests/security-regression-smoke.mjs`
- Extend: `tests/test_security_auth_regression.py`
- Modify only on reproduced finding: `backend/app.py`, frontend rendering component actually responsible.
**Interfaces:**
- Browser auth remains explicit Bearer in `Authorization`; no ambient auth cookie is introduced.
- CORS uses configured exact origins only; unconfigured origins receive no `Access-Control-Allow-Origin`.

- [ ] **Step 1: Pin CORS and CSRF posture at the API layer**

Use a TestClient/ASGI client with `CORS_ORIGINS=https://trusted.example` and assert:

```python
# trusted preflight
Origin: https://trusted.example
Access-Control-Request-Method: PUT
# => ACAO exactly https://trusted.example

# untrusted preflight
Origin: https://evil.example
# => no ACAO granting evil.example
```

Also assert state-changing routes still require an explicit `Authorization: Bearer ...` header and no `Set-Cookie` response establishes an auth session. This documents why cookie-style CSRF tokens are not added to the bearer-token architecture.

- [ ] **Step 2: Add browser XSS regression with hostile display data**

In `frontend/tests/security-regression-smoke.mjs`, mock `/api/users` with a username/name payload such as:

```javascript
const payload = `<img src=x onerror="globalThis.__pvnXss=1">`;
```

Open `/users`, assert the literal string is visible as text or escaped DOM content, `globalThis.__pvnXss` is unset, no `<script>` or attacker-created executable `<img onerror>` node is present, and no console/page error indicates script execution.

- [ ] **Step 3: Guard against dangerous rendering primitives**

Add a source assertion that `frontend/src` contains no unreviewed `dangerouslySetInnerHTML`, `document.write`, or direct assignment to `.innerHTML`. If an intentional use already exists later, it must be isolated and separately sanitized rather than globally exempted.
- [ ] **Step 4: Run API and browser-focused security checks**

```bash
python3 -m unittest tests.test_security_auth_regression -v
cd frontend
npm ci
npm run build
npm run preview -- --host 127.0.0.1 --port 4173 >/tmp/pvn-v114-vite.log 2>&1 &
VITE_PID=$!
trap 'kill "$VITE_PID" 2>/dev/null || true' EXIT
PV_UI_BASE_URL=http://127.0.0.1:4173/panel node tests/security-regression-smoke.mjs
```
Expected: PASS with no executed payload and no arbitrary-origin credential grant.

- [ ] **Step 5: Commit**

```bash
git add frontend/tests/security-regression-smoke.mjs tests/test_security_auth_regression.py backend/app.py frontend/src
git commit -m "test: lock browser and CORS security posture"
```

Only stage `backend/app.py` or frontend source when a reproduced finding required a fix.

---

### Task 6: Read-only Production security probe and sensitive-file checks

**Files:**
- Create: `scripts/pvnetwork-security-readonly-probe.py`
- Create: `tests/test_security_readonly_probe.py`
- Modify if necessary: `scripts/install-runtime-tools.sh`

**Interfaces:**
- CLI: `python3 scripts/pvnetwork-security-readonly-probe.py --base-url "$PUBLIC_BASE"`.
- Exit 0 only when all non-destructive checks pass; print one machine-readable line per check and `PVNETWORK_SECURITY_READONLY_PROBE=PASS` at the end.
- [ ] **Step 1: Write probe tests before the script**

Mock HTTP responses and assert the probe requires all of these without credentials:

```python
EXPECTED = {
    "/healthz": 200,
    "/openapi.json": 404,
    "/redoc": 404,
    "/api/users/": 401,
    "/api/security/": 401,
}
```

For `/healthz`, require the full **security headers** set: HSTS, CSP, `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, Referrer-Policy, and Permissions-Policy. Send `Origin: https://security-probe.invalid` and assert the response does not grant that origin.

- [ ] **Step 2: Implement the credential-free probe**

Use only Python stdlib `urllib.request`; do not read `.env`, browser storage, Git credentials, JWTs, API keys, or customer data. Resolve paths from the supplied base URL and record status/headers only.

```python
class ProbeFailure(RuntimeError):
    pass

def check_no_cors_grant(headers, origin):
    granted = headers.get("Access-Control-Allow-Origin", "")
    if granted in {origin, "*"}:
        raise ProbeFailure(f"untrusted CORS origin granted: {granted}")
```

The script must never send POST/PUT/PATCH/DELETE and must reject a base URL whose scheme is not HTTPS unless `--allow-http-loopback` is explicitly used for local tests.

- [ ] **Step 3: Add local sensitive-file mode checks to tests, not public output**

Test that installer/runtime contracts keep `.env`, staged candidate env, TOTP/secret material, restore uploads/status, and generated credential files at 0600/0700 boundaries already defined by their owners. Do not print secret contents or hashes of password/token values.

- [ ] **Step 4: Run and commit**

```bash
python3 -m unittest tests.test_security_readonly_probe tests.test_security_hardening -v
git add scripts/pvnetwork-security-readonly-probe.py tests/test_security_readonly_probe.py scripts/install-runtime-tools.sh
git commit -m "security: add read-only release probe"
```

---
### Task 7: CI gate, version metadata, and release-candidate documentation

**Files:**
- Modify: `.github/workflows/ci.yml`
- Modify: `VERSION`, `backend/version.py`, `pyproject.toml`, `manifest.json`
- Modify: `frontend/package.json`, `frontend/package-lock.json`
- Modify: `CHANGELOG.md`, `README.md`, `README.fa.md`, `ROADMAP.md`, `AGENTS.md`
- Create: `docs/RELEASE-NOTES-v1.0.14.md`
- Create: `docs/RELEASE-NOTES-v1.0.14.fa.md`

**Interfaces:**
- CI exposes a named `Security regression suite` gate plus browser security smoke.
- All version-bearing files must resolve to `1.0.14` before merge.

- [ ] **Step 1: Add an explicit Python security-regression CI gate**

Add after `Unit and governance tests`:

```yaml
- name: Security regression suite
  run: |
    python3 -m unittest \
      tests.test_security_proxy_ip \
      tests.test_security_auth_regression \
      tests.test_security_scope_regression \
      tests.test_security_input_regression \
      tests.test_security_readonly_probe -v
```

Keep dependency audit, Bandit, Router real handshake, full unit discovery, browser matrix, secret guard, and lifecycle checks unchanged.
- [ ] **Step 2: Add browser security smoke to the existing browser gate**

Append to the existing `Browser responsive smoke matrix` commands:

```bash
node tests/security-regression-smoke.mjs
```

The browser test runs against the local Vite preview with mocked APIs only; it must not call Production or use real credentials.

- [ ] **Step 3: Update all version metadata to 1.0.14**

Use the existing file conventions:

```bash
printf '1.0.14\n' > VERSION
python3 - <<'PY'
from pathlib import Path
p = Path('backend/version.py')
p.write_text('__version__ = "1.0.14"\n', encoding='utf-8')
PY
cd frontend && npm version 1.0.14 --no-git-tag-version && cd ..
```

Update `pyproject.toml`, `manifest.json`, README badges/current-release links, and the changelog/roadmap consistently. `manifest.json.release_asset` becomes `pvnetwork-panel-v1.0.14.tar.gz`.

- [ ] **Step 4: Write bilingual release-candidate notes with actual reproduced findings only**

The notes must distinguish:
- reproduced and fixed findings;
- tested controls that were already safe;
- architectural findings deferred with their `PVN-xxx` follow-up;
- Production safety boundary and rollout gates.

Do not call a static suspicion a vulnerability and do not publish live domains, IPs, credentials, customer data, or screenshots containing them.
- [ ] **Step 5: Run the complete local release gate**

```bash
python3 -m compileall -q backend tests
python3 -m py_compile scripts/*.py
python3 -m unittest discover -s tests -v
cd frontend
npm ci
npm run lint -- --quiet
npm run build
npm audit --omit=dev --audit-level=high
cd ..
git diff --check
```

Then run the focused browser security smoke through the same local preview setup used in Task 5. Expected: every command succeeds.

- [ ] **Step 6: Commit and push the release candidate**

```bash
git add .github/workflows/ci.yml VERSION backend/version.py pyproject.toml manifest.json \
  frontend/package.json frontend/package-lock.json CHANGELOG.md README.md README.fa.md \
  ROADMAP.md AGENTS.md docs/RELEASE-NOTES-v1.0.14.md docs/RELEASE-NOTES-v1.0.14.fa.md
git commit -m "release: prepare v1.0.14 security regression"
git push -u origin HEAD
```

Open a PR to `main`, require exact-head GitHub CI success, review findings against the spec, and merge only the exact reviewed head SHA. After merge, require the push-triggered `main` CI to succeed again before any Production mutation.

---

### Task 8: Production rollout, evidence closure, immutable v1.0.14 release

**Files:**
- Modify after Production verification: `AGENTS.md`, `ROADMAP.md`, and release notes only if evidence/status changed.
- No additional runtime feature code belongs in this task.

**Interfaces:**
- Canary: exact merged-main candidate on loopback port `19002`.
- Canonical panel: `19001`.
- Retirement gate: `/usr/local/sbin/pvnetwork-canary-retire-guard` must output `CANARY_RETIRE_SAFE=YES`.
- [ ] **Step 1: Capture and verify the rollback point before mutation**

```bash
PANEL_PID=$(systemctl show -p MainPID --value pvnetwork-panel.service)
NODE_PID=$(systemctl show -p MainPID --value ov-node.service)
OPENVPN_PID=$(systemctl show -p MainPID --value openvpn-server@server.service)
sha256sum /etc/openvpn/server/server.conf > /tmp/pvn114-openvpn.sha256
[ ! -f /etc/openvpn/server/pvnetwork-router.conf ] || \
  sha256sum /etc/openvpn/server/pvnetwork-router.conf > /tmp/pvn114-router.sha256
/usr/local/sbin/pvnetwork-panel-backup
```

Locate the newly created timestamped backup directory, require `RESTORE_TEST_OK`, run `sha256sum -c SHA256SUMS` inside it, and run `pg_restore -l database.dump >/dev/null`. Save Nginx config and the baseline service PIDs/hashes into a root-only evidence directory.

- [ ] **Step 2: Derive the public endpoint without writing it to tracked files**

```bash
NGINX_SITE=$(grep -Rl 'proxy_pass http://127.0.0.1:19001' /etc/nginx/sites-enabled | head -1)
test -n "$NGINX_SITE"
SERVER_NAME=$(awk '$1=="server_name" {gsub(";","",$2); print $2; exit}' "$NGINX_SITE")
test -n "$SERVER_NAME"
PUBLIC_BASE="https://$SERVER_NAME"
```

Keep `PUBLIC_BASE` only in the shell/evidence process; never add the resolved value to Git, release notes, or public logs.

- [ ] **Step 3: Start exact merged-main canary on 19002 and run adversarial checks there**

Build the frontend with the live panel path, launch the exact merged-main candidate with an isolated canary env overriding only `PORT=19002`, and require local `/healthz` to report `1.0.14`. Run all state-changing security-regression tests only against the isolated test DB/canary context; never point destructive fixtures at the Production database.
- [ ] **Step 4: Switch public traffic to canary, update canonical, and cut back safely**

Use the established atomic Nginx edit to change only the panel upstream from `19001` to `19002`, run `nginx -t`, reload Nginx, and verify `$PUBLIC_BASE/healthz`, panel root, and `/users` all return 200 from v1.0.14.

Sync the exact merged-main tree to `/opt/pvnetwork-panel` without overwriting `.env`, runtime state, PostgreSQL data, certificates, OpenVPN files, or Node files. Rebuild the frontend with the live path and restart only `pvnetwork-panel.service`; require `http://127.0.0.1:19001/healthz` to report v1.0.14.

Restore the Nginx site file to canonical `19001` **without manually retiring the canary**, then run:

```bash
/usr/local/sbin/pvnetwork-canary-retire-guard \
  --nginx-site "$NGINX_SITE" \
  --public-health-url "$PUBLIC_BASE/healthz"
```

Require `CANARY_RETIRE_SAFE=YES`, `ACTIVE_PROXY_PORTS=19001`, and both local/public HTTP 200 before terminating the verified canary PID.

- [ ] **Step 5: Run non-destructive Production security verification**

```bash
python3 /opt/pvnetwork-panel/scripts/pvnetwork-security-readonly-probe.py \
  --base-url "$PUBLIC_BASE"
/usr/local/sbin/pvnetwork-panel-smoke-test
```

Recheck panel, Node, and OpenVPN PIDs; Node/OpenVPN must equal baseline values. Recheck both OpenVPN config hashes. Verify Nginx has no active `19002` upstream and public health/UI/users remain 200 after canary termination.

Run login-rate-limit sanity only against loopback with a reserved synthetic XFF address so no real client bucket is touched: issue unauthenticated `GET /api/login` requests to `http://127.0.0.1:19001` with final XFF `198.51.100.250`, stop at the configured login limit + 1, and require the terminal response to be 429 with `Retry-After: 60`. Clear only that synthetic in-process bucket by restarting the panel only if a later release step already requires it; otherwise let it expire naturally for 60 seconds.

- [ ] **Step 6: Record Production evidence in a docs-only closure commit**

Update `AGENTS.md`, `ROADMAP.md`, and v1.0.14 release notes with reproduced findings, fixes, safe controls, deferred findings, CI run IDs, rollback/canary evidence, unchanged Node/OpenVPN evidence, and the read-only Production probe result. Do not record live hostnames, IPs, secrets, customer identifiers, or credential material.
- [ ] **Step 7: Merge evidence and require final main CI**

Push the docs-only closure branch, open a PR to `main`, require exact-head CI success, merge the reviewed head, and then require the push-triggered final `main` CI to succeed. The tag target is the resulting final main commit, not the earlier runtime merge commit.

- [ ] **Step 8: Create immutable tag and sanitized artifact**

```bash
FINAL_SHA=$(git rev-parse origin/main)
git tag -a v1.0.14 "$FINAL_SHA" -m "PVNetwork Panel v1.0.14 - PVN-585 security regression"
git push origin v1.0.14
rm -rf /root/pvnetwork-release-v1.0.14
mkdir -p /root/pvnetwork-release-v1.0.14
git archive --format=tar --prefix=pvnetwork-panel-v1.0.14/ v1.0.14 | \
  gzip -n > /root/pvnetwork-release-v1.0.14/pvnetwork-panel-v1.0.14.tar.gz
cd /root/pvnetwork-release-v1.0.14
sha256sum pvnetwork-panel-v1.0.14.tar.gz > pvnetwork-panel-v1.0.14.tar.gz.sha256
```

Extract the artifact into a temporary directory and run the same private-material/secret guard as CI. Require `VERSION=1.0.14`, no forbidden `.ovpn/.key/.pem/.p12/.pfx/.db/.sqlite*` entries, and no real `.env`.

- [ ] **Step 9: Publish Release and verify from GitHub**

Use the established credential-safe release publisher that obtains the GitHub credential inside its process and never prints it. Publish the two assets above with `docs/RELEASE-NOTES-v1.0.14.md` as the body.

Download both public assets from the GitHub Release URL into a fresh directory, run `sha256sum -c`, inspect archive entry count, recheck `VERSION=1.0.14`, rerun the forbidden-private-material inventory, and verify tag `v1.0.14` resolves exactly to `FINAL_SHA`.

Expected terminal evidence:

```text
PUBLIC_REDOWNLOAD_VERIFY=PASS
VERSION=1.0.14
FORBIDDEN_PRIVATE_FILES=0
```

- [ ] **Step 10: Mark PVN-585 released only after all gates pass**

Update no code after tag publication. If final public re-download verification fails, do not move/rewrite the tag or replace assets silently; publish a new patch release after correcting the defect.
