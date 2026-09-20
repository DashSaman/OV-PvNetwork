# PVN-032 / v1.0.12 Main Admin & Panel Path Runtime Settings Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let an authenticated interactive `main_admin` change the panel path, main-admin username, and main-admin password from Security Settings with automatic canary validation, rollback, five-minute old-path redirect, and zero VPN/Node interruption.

**Architecture:** Keep `.env` as the credential/path source of truth, add generation-bound main-admin JWTs, expose a focused panel-settings router, and delegate build/switch/rollback to a detached helper that survives the canonical Uvicorn restart. Build the candidate frontend into a staging directory, validate a candidate panel on `127.0.0.1:19002`, then atomically switch `.env` and `frontend/dist`; a transition middleware provides the five-minute 307 redirect.

**Tech Stack:** FastAPI, Pydantic Settings, SQLAlchemy/PostgreSQL, PyJWT, passlib/bcrypt, React 19, Axios, Vite, systemd, Nginx, Python `fcntl`/`subprocess`/filesystem primitives, unittest/Playwright/GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-20-pvn-032-admin-settings-design.md`

## Global Constraints
- Target release is exactly `v1.0.12`; one Production-visible task: `PVN-032`.
- Existing OpenVPN, Router OpenVPN, Node, tunnel, subscription, routing, and device-limit behavior must not change.
- Only `pvnetwork-panel.service` may be restarted during apply/rollback; Nginx and VPN/Node services must not be restarted.
- Current password is required for every mutation; plaintext current/new passwords must never reach disk, logs, job state, audit resource, or subprocess arguments.
- Old panel path redirects with HTTP 307 for exactly 300 seconds, then naturally returns 404.
- A path-only change preserves main-admin auth generation; username/password changes rotate it and invalidate old main-admin browser JWTs.
- Existing TOTP state follows a renamed main admin and is restored on rollback.
- Production rollout requires verified backup, canary on port 19002, PID/config-hash evidence, full CI, sanitized artifact, SHA256, and post-publish re-download verification.

## Review Focus
- Concurrent apply requests must produce one accepted change and one HTTP 409 without two helpers racing.
- A stale/tampered change-status token must never reveal job state; a valid token must continue polling after old admin JWT invalidation.
- Candidate build or candidate health/asset/auth failure must leave live `.env`, live `frontend/dist`, and canonical PID state unchanged.
- Canonical verification failure after switch must restore the exact previous `.env`, dist tree, auth generation, and `PrincipalSecurity` username.
- Path values differing only by case or colliding with server/subscription routes must be rejected before any staging or restart.

## File Structure
- Create `backend/panel_runtime_settings.py`: validation, state paths, safe JSON writes, status-token helpers, env parsing/rendering, lock/spawn helpers.
- Create `backend/panel_redirect.py`: five-minute previous-path redirect middleware with suffix/query preservation.
- Create `backend/routers/panel_settings.py`: main-admin-only GET/apply/job-status API.
- Create `scripts/pvnetwork-panel-settings-apply.py`: detached build/canary/switch/verify/rollback worker.
- Create `scripts/migrate_main_admin_generation.py`: idempotent existing-install generation bootstrap.
- Modify `backend/auth/auth.py`, `backend/config.py`, `backend/app.py`, `backend/routers/__init__.py`, `frontend/vite.config.js`, `frontend/src/services/api.js`, `frontend/src/context/AuthContext.jsx`, and `frontend/src/pages/SecuritySettings.jsx`.
- Modify `.env.example`, `install-local.sh`, `scripts/manage.sh`, `scripts/install-runtime-tools.sh`, translations, tests, VERSION/changelog/release docs/ledger.

---

### Task 1: Generation-bound main-admin authentication and migration

**Files:**
- Modify: `backend/config.py`
- Modify: `backend/auth/auth.py`
- Create: `scripts/migrate_main_admin_generation.py`
- Modify: `.env.example`
- Modify: `install-local.sh`
- Modify: `scripts/manage.sh`
- Test: `tests/test_main_admin_generation.py`

**Interfaces:**
- Produces: `config.MAIN_ADMIN_AUTH_GENERATION: str`.
- Produces: `create_access_token(data: dict, expires_delta: timedelta | None = None) -> str` with `gen` included for `main_admin` payloads.
- Produces: `mint_main_admin_token(username: str, generation: str) -> str` for replacement-token creation.
- Produces: `ensure_generation(env_path: Path) -> str` in the migration script.

- [ ] **Step 1: Write failing auth-generation tests**

```python
def test_old_main_admin_generation_is_rejected(client, main_admin_token):
    config.MAIN_ADMIN_AUTH_GENERATION = "gen-new"
    response = client.get("/api/security/", headers={"Authorization": f"Bearer {main_admin_token}"})
    assert response.status_code == 401

def test_main_admin_subject_must_match_config(client, token_for):
    response = client.get("/api/security/", headers={"Authorization": f"Bearer {token_for('old-admin', 'main_admin', gen=config.MAIN_ADMIN_AUTH_GENERATION)}"})
    assert response.status_code == 401
```

- [ ] **Step 2: Run tests and verify RED**

Run: `./.venv/bin/python -m unittest tests.test_main_admin_generation -v`
Expected: FAIL because `MAIN_ADMIN_AUTH_GENERATION` and generation checks do not exist.

- [ ] **Step 3: Add generation config and JWT enforcement**

```python
# backend/config.py
MAIN_ADMIN_AUTH_GENERATION: str = "legacy"

# backend/auth/auth.py, after JWT decode
if user_type == "main_admin":
    if username != config.ADMIN_USERNAME:
        raise credentials_exception
    if payload.get("gen") != config.MAIN_ADMIN_AUTH_GENERATION:
        raise credentials_exception
```

Use a helper so login/replacement token construction cannot diverge:

```python
def mint_main_admin_token(username: str, generation: str) -> str:
    return create_access_token({"sub": username, "type": "main_admin", "gen": generation})
```

Main-admin login calls `mint_main_admin_token`; delegated-admin login keeps the existing payload shape.

- [ ] **Step 4: Add idempotent generation bootstrap**

```python
def ensure_generation(env_path: Path) -> str:
    values = parse_env(env_path)
    current = values.get("MAIN_ADMIN_AUTH_GENERATION", "").strip()
    if current:
        return current
    value = secrets.token_urlsafe(24)
    rewrite_env_key_atomic(env_path, "MAIN_ADMIN_AUTH_GENERATION", value)
    return value
```

`install-local.sh` writes a generated value during fresh install; `scripts/manage.sh build_panel()` runs the migration immediately after `migrate_admin_password_hash.py`. `.env.example` gains `MAIN_ADMIN_AUTH_GENERATION=CHANGE_ME_GENERATED`.

- [ ] **Step 5: Run focused and existing auth tests**

Run: `./.venv/bin/python -m unittest tests.test_main_admin_generation tests.test_admin_password_migration tests.test_security_hardening -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/config.py backend/auth/auth.py scripts/migrate_main_admin_generation.py .env.example install-local.sh scripts/manage.sh tests/test_main_admin_generation.py
git commit -m "feat: bind main admin sessions to auth generation"
```

### Task 2: Runtime-settings validation, job state, status tokens, and lock handoff

**Files:**
- Create: `backend/panel_runtime_settings.py`
- Test: `tests/test_panel_runtime_settings.py`

**Interfaces:**
- Produces: `validate_admin_username(value: str, delegated_names: set[str]) -> str`.
- Produces: `validate_panel_path(value: str, subscription_path: str) -> str`.
- Produces: `build_candidate_env(live_env: Path, new_username: str | None, new_password_hash: str | None, new_path: str | None, new_generation: str | None) -> str`.
- Produces: `write_job_state(change_id: str, payload: dict) -> None`, `read_job_state(change_id: str) -> dict | None`.
- Produces: `write_transition_state(payload: dict) -> None`, `load_transition_state() -> dict | None` for the non-secret old/new path redirect state.
- Produces: `mint_change_status_token(change_id: str, ttl_seconds: int = 900) -> str`, `verify_change_status_token(token: str, change_id: str) -> None`.
- Produces: `SECRET_KEYS: set[str]`, `acquire_apply_lock() -> int`, and `spawn_apply_helper(change_id: str, staging_dir: Path, lock_fd: int) -> int`.

- [ ] **Step 1: Write failing validation/state/security tests**

```python
def test_reserved_and_case_colliding_paths_are_rejected():
    for value in ["api", "API", "healthz", "assets", "sub"]:
        with self.assertRaises(ValueError):
            validate_panel_path(value, "sub")

def test_job_state_rejects_secret_keys(tmp_path, monkeypatch):
    monkeypatch.setattr(runtime, "JOB_DIR", tmp_path)
    with self.assertRaises(ValueError):
        write_job_state("abc", {"status": "queued", "new_password": "secret"})
```

- [ ] **Step 2: Run tests and verify RED**

Run: `./.venv/bin/python -m unittest tests.test_panel_runtime_settings -v`
Expected: FAIL because the module/functions do not exist.

- [ ] **Step 3: Implement exact validation rules and secret-free state writes**

```python
PATH_RE = re.compile(r"^[A-Za-z0-9_-]{3,64}$")
RESERVED = {"api", "healthz", "doc", "redoc", "openapi.json", "assets"}
SECRET_KEYS = {"current_password", "new_password", "password_hash", "jwt", "token", "env"}

def validate_admin_username(value: str, delegated_names: set[str]) -> str:
    value = value.strip()
    if not 3 <= len(value) <= 64 or any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
        raise ValueError("Username must be 3-64 printable characters")
    if value.casefold() in {name.casefold() for name in delegated_names}:
        raise ValueError("Username collides with an existing administrator")
    return value

def validate_panel_path(value: str, subscription_path: str) -> str:
    value = value.strip()
    if not PATH_RE.fullmatch(value):
        raise ValueError("Panel path must be 3-64 letters, digits, '_' or '-'")
    blocked = RESERVED | {subscription_path.casefold()}
    if value.casefold() in blocked:
        raise ValueError("Panel path collides with a reserved route")
    return value
```

`write_job_state` recursively rejects secret-key names, writes JSON to a same-directory temporary file with mode `0600`, fsyncs it, then `os.replace()`s it into `/var/lib/pvnetwork-panel/panel-settings-jobs/<change_id>.json`.

- [ ] **Step 4: Implement change-status JWT and inherited lock**

Status token claims are exactly `{"typ":"panel-settings-status","cid":change_id,"exp":...}` signed with `config.JWT_SECRET_KEY`. `verify_change_status_token` rejects wrong type, wrong change id, expiry, or invalid signature.

`acquire_apply_lock()` opens `/var/lib/pvnetwork-panel/panel-settings.lock`, takes `fcntl.flock(fd, LOCK_EX | LOCK_NB)`, and raises `ApplyBusy` on contention. `spawn_apply_helper()` calls the worker with `pass_fds=(lock_fd,)`, `start_new_session=True`, no password/JWT arguments, and redirects output to the job log.

- [ ] **Step 5: Add review-focus tests for lock, tampered token, and candidate env rendering**

Verify second lock acquisition fails, tampered/expired tokens fail, path-only candidate env preserves `MAIN_ADMIN_AUTH_GENERATION`, and username/password candidate env rotates only to the supplied generation.

- [ ] **Step 6: Run focused tests and commit**

Run: `./.venv/bin/python -m unittest tests.test_panel_runtime_settings -v`
Expected: PASS.

```bash
git add backend/panel_runtime_settings.py tests/test_panel_runtime_settings.py
git commit -m "feat: add safe panel runtime settings primitives"
```

### Task 3: Detached build/canary/switch/rollback worker

**Files:**
- Create: `scripts/pvnetwork-panel-settings-apply.py`
- Modify: `frontend/vite.config.js`
- Modify: `backend/app.py`
- Modify: `scripts/install-runtime-tools.sh`
- Test: `tests/test_panel_settings_apply_worker.py`

**Interfaces:**
- Worker CLI invocation is exactly `pvnetwork-panel-settings-apply --change-id "$CHANGE_ID" --staging-dir "$STAGING_DIR" --lock-fd "$LOCK_FD"`; no secret values on argv.
- `backend/app.py` consumes optional `PVNETWORK_FRONTEND_DIST`; absent means existing `frontend/dist`.
- Vite consumes optional `PVNETWORK_BUILD_OUTDIR`; absent means `dist`.
- Worker job stages: `building`, `canary`, `switching`, `verifying`, `complete`, `rolled_back`.

- [ ] **Step 1: Write worker contract tests with fake service/build adapters**

```python
def test_build_failure_never_mutates_live_files(worker_harness):
    before = worker_harness.snapshot_live()
    result = worker_harness.run(build_rc=1)
    assert result["status"] == "rolled_back"
    assert worker_harness.snapshot_live() == before
    assert worker_harness.restart_calls == []

def test_post_switch_failure_restores_exact_env_and_dist(worker_harness):
    before = worker_harness.snapshot_live()
    result = worker_harness.run(canonical_health=False)
    assert result["status"] == "rolled_back"
    assert worker_harness.snapshot_live() == before
    assert worker_harness.restart_calls == ["pvnetwork-panel.service", "pvnetwork-panel.service"]
```

- [ ] **Step 2: Run worker tests and verify RED**

Run: `./.venv/bin/python -m unittest tests.test_panel_settings_apply_worker -v`
Expected: FAIL because worker hooks and staging support do not exist.

- [ ] **Step 3: Make build and candidate frontend paths injectable**

```js
// frontend/vite.config.js
const outDir = process.env.PVNETWORK_BUILD_OUTDIR || 'dist'
// ...
build: { outDir }
```

```python
# backend/app.py
frontend_build_path = os.getenv(
    "PVNETWORK_FRONTEND_DIST",
    os.path.join(os.path.dirname(__file__), "..", "frontend", "dist"),
)
```

- [ ] **Step 4: Implement worker preflight without live mutation**

The worker re-hashes the current live `.env` and compares it with `expected_env_sha256` stored in the secret-free job descriptor; mismatch aborts before build. It requires `frontend/node_modules/.bin/vite` to exist, runs `npm run build` with candidate `URLPATH`, `VITE_URLPATH`, and `PVNETWORK_BUILD_OUTDIR=<staging>/dist`, then starts candidate Uvicorn on `127.0.0.1:19002` with candidate env values and `PVNETWORK_FRONTEND_DIST=<staging>/dist`.

Candidate checks: `/healthz` is 200, `/<new_path>` is 200, parsed JS/CSS asset is 200, reserved `/api` routing remains API-owned, and a candidate main-admin JWT with the candidate username/generation reaches `GET /api/security/panel-settings` without bypassing TOTP configuration.

- [ ] **Step 5: Implement atomic switch and exact rollback**

Use `os.replace()` for the candidate `.env`. For dist, use Linux `renameat2(RENAME_EXCHANGE)` via `ctypes` so live and staged directories exchange atomically on the same filesystem; if unsupported, fail preflight rather than degrading to a non-atomic switch. Before mutation, copy `.env`, dist, transition state, service metadata, and checksums to `/var/backups/pvnetwork-panel/runtime-settings/<change_id>/`.

After switch: write transition metadata, `systemctl restart pvnetwork-panel.service`, then poll canonical health/new HTML/asset for at most 30 seconds. On failure, exchange dist back, restore `.env`, restore previous `PrincipalSecurity` username if changed, restart the panel once, verify the previous path, and mark `rolled_back`.

- [ ] **Step 6: Guarantee service isolation**

The worker must contain an allowlist assertion:

```python
ALLOWED_RESTARTS = {"pvnetwork-panel.service"}
def restart_service(name: str) -> None:
    if name not in ALLOWED_RESTARTS:
        raise RuntimeError(f"forbidden service restart: {name}")
```

Tests grep/patch subprocess calls and fail if OpenVPN, Node, Router OpenVPN, Nginx, tunnel, or firewall restart/reload commands occur.

- [ ] **Step 7: Run worker tests and commit**

Run: `./.venv/bin/python -m unittest tests.test_panel_settings_apply_worker -v`
Expected: PASS.

```bash
git add scripts/pvnetwork-panel-settings-apply.py frontend/vite.config.js backend/app.py scripts/install-runtime-tools.sh tests/test_panel_settings_apply_worker.py
git commit -m "feat: add atomic panel settings apply worker"
```

### Task 4: Old-path redirect middleware

**Files:**
- Create: `backend/panel_redirect.py`
- Modify: `backend/app.py`
- Test: `tests/test_panel_path_redirect.py`

**Interfaces:**
- Produces: `PanelPathTransitionMiddleware` reading `/var/lib/pvnetwork-panel/panel-path-transition.json`.
- Transition schema: `old_path`, `new_path`, `redirect_expires_at`, `change_id` only.

- [ ] **Step 1: Write RED tests for exact redirect window and suffix/query preservation**

```python
def test_old_path_redirects_before_expiry(client, transition_file, clock):
    transition_file(old_path="old", new_path="new", expires=clock.now + 300)
    r = client.get("/old/users?tab=active", follow_redirects=False)
    assert r.status_code == 307
    assert r.headers["location"] == "/new/users?tab=active"

def test_old_path_is_not_redirected_at_expiry(client, transition_file, clock):
    transition_file(old_path="old", new_path="new", expires=clock.now)
    assert client.get("/old/users", follow_redirects=False).status_code == 404
```

- [ ] **Step 2: Run and verify RED**
Run: `./.venv/bin/python -m unittest tests.test_panel_path_redirect -v`
Expected: FAIL because middleware is absent.

- [ ] **Step 3: Implement bounded redirect middleware**

```python
class PanelPathTransitionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        state = load_transition_state()
        if state and time.time() < state["redirect_expires_at"]:
            old = "/" + state["old_path"]
            path = request.url.path
            if path == old or path.startswith(old + "/"):
                suffix = path[len(old):]
                target = "/" + state["new_path"] + suffix
                if request.url.query:
                    target += "?" + request.url.query
                return RedirectResponse(target, status_code=307)
        return await call_next(request)
```

Register before SPA routing. Add negative tests proving `/api`, `/healthz`, subscription routes, unrelated prefixes, and `oldish/...` never redirect.

- [ ] **Step 4: Run tests and commit**

Run: `./.venv/bin/python -m unittest tests.test_panel_path_redirect -v`
Expected: PASS.

```bash
git add backend/panel_redirect.py backend/app.py tests/test_panel_path_redirect.py
git commit -m "feat: redirect previous panel path during grace window"
```

### Task 5: Panel-settings API, re-authentication, TOTP migration, and audit

**Files:**
- Create: `backend/routers/panel_settings.py`
- Modify: `backend/routers/__init__.py`
- Modify: `backend/panel_runtime_settings.py`
- Modify: `scripts/pvnetwork-panel-settings-apply.py`
- Test: `tests/test_panel_settings_api.py`

**Interfaces:**
- `GET /api/security/panel-settings` returns `{username, panel_path, redirect, active_change}`.
- `POST /api/security/panel-settings/apply` body: `{current_password, new_username?, new_password?, new_path?}`.
- Apply response: `{change_id, status_token, pending_access_token?, target_path}`.
- `GET /api/security/panel-settings/jobs/{change_id}` authorizes `X-PVNetwork-Change-Token` and returns secret-free job state.

- [ ] **Step 1: Write RED API authorization/re-auth tests**

```python
def test_api_token_cannot_apply_panel_settings(api_token_client):
    r = api_token_client.post('/api/security/panel-settings/apply', json={"current_password":"x","new_path":"nextpanel"})
    assert r.status_code == 403

def test_wrong_current_password_is_noop(main_admin_client, snapshot_runtime):
    before = snapshot_runtime()
    r = main_admin_client.post('/api/security/panel-settings/apply', json={"current_password":"wrong","new_path":"nextpanel"})
    assert r.status_code == 401
    assert snapshot_runtime() == before
```

Also pin: delegated admin 403, no-op change 422, invalid username/path/password 422, existing delegated username collision 422, concurrent apply 409.

- [ ] **Step 2: Run and verify RED**
Run: `./.venv/bin/python -m unittest tests.test_panel_settings_api -v`
Expected: FAIL because router does not exist.

- [ ] **Step 3: Implement focused request models and interactive-admin guard**

```python
class PanelSettingsApplyIn(BaseModel):
    current_password: str = Field(min_length=1, max_length=1024)
    new_username: str | None = None
    new_password: str | None = None
    new_path: str | None = None

def require_interactive_main_admin(user: dict) -> None:
    if user.get("type") != "main_admin" or user.get("auth_kind") == "api_token":
        raise HTTPException(403, "Interactive main administrator required")
```

- [ ] **Step 4: Implement apply staging and pending-token semantics**

On apply: acquire the non-blocking apply lock first; while holding it, re-read live `.env`, verify current password against its current hash/config, load delegated-admin names, normalize/validate requested values, and reject if nothing changes (including path changes that differ only by case). New passwords must be minimum 12 characters and `verify_password(new_password, current_hash)` must be false; otherwise return 422. Compute `new_generation = secrets.token_urlsafe(24)` only if username/password changes; hash `new_password` in memory; build candidate env text; persist candidate env as mode `0600` inside the staging directory; persist only hashes/paths/field names in the job descriptor; spawn helper with the inherited lock fd; close the parent copy only after successful spawn. On any validation/staging/spawn failure, close the lock fd and remove the incomplete staging directory.

If credentials change, return `pending_access_token=mint_main_admin_token(target_username, target_generation)`. If only path changes, return no replacement token.

- [ ] **Step 5: Preserve TOTP on username change and restore on rollback**

Before helper spawn, record only the current `PrincipalSecurity.id` and old/new username in the job descriptor. During switch the worker updates exactly that `main_admin` row username in the same controlled phase; rollback restores the old username. If no row exists, no row is created solely by rename.

- [ ] **Step 6: Add explicit result audit without secrets**

Worker writes a terminal `AuditLog` row using action `SETTINGS_APPLY`; resource format is bounded and non-secret, e.g. `panel-settings:<change_id>:path=hajsaman->newpath:username=changed:result=complete`. Use a deterministic terminal request id `settings-<change_id>-complete` or `settings-<change_id>-rollback` to avoid duplicate audit rows on helper retry.

- [ ] **Step 7: Implement status endpoint independent of old JWT**

`GET .../jobs/{change_id}` reads only `X-PVNetwork-Change-Token`, calls `verify_change_status_token`, and does not depend on `get_current_user`. It still passes normal IP allowlist/rate-limit middleware. Do not return staging paths, hashes, environment contents, JWTs, or logs.

- [ ] **Step 8: Run API tests and commit**

Run: `./.venv/bin/python -m unittest tests.test_panel_settings_api tests.test_panel_runtime_settings -v`
Expected: PASS.

```bash
git add backend/routers/panel_settings.py backend/routers/__init__.py backend/panel_runtime_settings.py scripts/pvnetwork-panel-settings-apply.py tests/test_panel_settings_api.py
git commit -m "feat: expose authenticated panel runtime settings API"
```

### Task 6: Security Settings UI, pending-token handoff, and restart-safe polling

**Files:**
- Modify: `frontend/src/services/api.js`
- Modify: `frontend/src/context/AuthContext.jsx`
- Modify: `frontend/src/pages/SecuritySettings.jsx`
- Modify: `frontend/src/lang/fa.json`
- Modify: `frontend/src/lang/en.json`
- Mirror new keys into remaining locale JSON files using English fallback text.
- Create: `frontend/tests/panel-settings-smoke.mjs`
- Modify: `.github/workflows/ci.yml`

**Interfaces:**
- `apiClient` request config supports `skipAuth: true` and `skipUnauthorizedReload: true`.
- Auth context produces `stageReplacementToken(token)`, `promoteReplacementToken()`, `discardReplacementToken()`.
- Pending token storage key: `pvnPendingAuthToken` in `sessionStorage`; promoted token remains `authToken` in `localStorage`.
- Restart-resume envelope key: `pvnPanelSettingsChange` in `sessionStorage`, containing only `change_id`, `status_token`, `target_path`, `previous_path`, and timestamps; it is cleared on terminal completion/rollback.

- [ ] **Step 1: Write Playwright RED smoke covering confirmation, progress, token promotion, navigation, rollback, mobile layout**

```js
await page.route('**/api/security/panel-settings/jobs/**', async route => {
  await route.fulfill({json: {success:true, data:{status:'complete', new_path:'newpanel'}}})
})
await page.getByLabel('Current password').fill('current-secret')
await page.getByLabel('Panel path').fill('newpanel')
await page.getByRole('button', {name:'Apply changes'}).click()
await page.getByRole('button', {name:'Confirm'}).click()
await page.waitForURL('**/newpanel/security')
```

Add a second mocked flow ending in `rolled_back` and assert original URL/session remains; run once at desktop and once at 390×844.

- [ ] **Step 2: Run smoke and verify RED**

Run: `cd frontend && node tests/panel-settings-smoke.mjs`
Expected: FAIL because the card, polling, and token-handoff helpers are absent.

- [ ] **Step 3: Add opt-out auth behavior for job polling**

```js
apiClient.interceptors.request.use(config => {
  if (!config.skipAuth) {
    const token = localStorage.getItem('authToken')
    if (token) config.headers.Authorization = `Bearer ${token}`
  }
  return config
})
```

The 401 response interceptor must skip forced logout/reload when `error.config.skipUnauthorizedReload === true`. It must also suppress automatic reload while a valid `pvnPanelSettingsChange` envelope exists, so the old JWT becoming invalid during a credential rotation cannot destroy the in-progress handoff; terminal completion/rollback clears the envelope and restores normal 401 handling.

- [ ] **Step 4: Add pending replacement-token helpers to AuthContext**

```js
const stageReplacementToken = token => sessionStorage.setItem('pvnPendingAuthToken', token)
const promoteReplacementToken = () => {
  const pending = sessionStorage.getItem('pvnPendingAuthToken')
  if (!pending) return
  localStorage.setItem('authToken', pending)
  localStorage.setItem('userRole', decodeJwtPayload(pending).type)
  sessionStorage.removeItem('pvnPendingAuthToken')
  setToken(pending)
  setUserRole(decodeJwtPayload(pending).type)
}
const discardReplacementToken = () => sessionStorage.removeItem('pvnPendingAuthToken')
```

Expose all three helpers via context.

- [ ] **Step 5: Add Panel & Main Admin card and progress state machine**

Fields: current username/path (read-only context), new username, new password + confirmation, new path, current password. Require current password client-side; validate password confirmation; show a confirmation summary before POST. After POST, persist the secret-bearing handoff only in `sessionStorage` as `pvnPanelSettingsChange` plus `pvnPendingAuthToken`; never localStorage or logs. Poll every 750 ms with `X-PVNetwork-Change-Token`, `skipAuth:true`, `skipUnauthorizedReload:true`, and bounded network retry for 45 seconds. On Security Settings mount, resume polling from a non-expired change envelope so an accidental reload during the controlled restart does not strand the browser.

On `complete`: promote pending token if present, clear progress state, and if path changed call `window.location.assign('/' + targetPath + '/security')`. On `rolled_back`: discard pending token, preserve original localStorage token, show rollback reason, and navigate to the previous path only if the browser had already moved.

- [ ] **Step 6: Run frontend checks and commit**

Run: `cd frontend && npm run lint && npm run build && node tests/panel-settings-smoke.mjs`
Expected: PASS with no console/page errors in both viewports.

```bash
git add frontend/src/services/api.js frontend/src/context/AuthContext.jsx frontend/src/pages/SecuritySettings.jsx frontend/src/lang/*.json frontend/tests/panel-settings-smoke.mjs .github/workflows/ci.yml
git commit -m "feat: add restart-safe panel settings UI"
```

### Task 7: Full regression, production-safety contracts, docs, version, and release preparation

**Files:**
- Create: `tests/test_panel_settings_production_contract.py`
- Modify: `VERSION`
- Modify: `backend/version.py`
- Modify: `frontend/package.json`
- Modify: `frontend/package-lock.json`
- Modify: `pyproject.toml`
- Modify: `manifest.json`
- Modify: `CHANGELOG.md`
- Modify: `README.md`
- Modify: `README.fa.md`
- Modify: `AGENTS.md`
- Modify: `ROADMAP.md`
- Create: `docs/RELEASE-NOTES-v1.0.12.md`
- Create: `docs/RELEASE-NOTES-v1.0.12.fa.md`

**Interfaces:**
- Release version everywhere: `1.0.12`.
- Rollback evidence directory pattern: `/root/pvnetwork-deploy-backups/v1.0.12-pvn032-<timestamp>`.

- [ ] **Step 1: Add production-safety contract tests**

```python
def test_apply_worker_never_restarts_vpn_or_node_services():
    src = Path('scripts/pvnetwork-panel-settings-apply.py').read_text()
    assert 'ALLOWED_RESTARTS = {"pvnetwork-panel.service"}' in src
    for forbidden in ['openvpn-server@server.service', 'ov-node.service', 'openvpn-server@pvnetwork-router.service']:
        assert f'restart {forbidden}' not in src

def test_runtime_state_contract_contains_no_secret_fields():
    src = Path('backend/panel_runtime_settings.py').read_text()
    from backend import panel_runtime_settings as runtime
    assert {'current_password', 'new_password', 'password_hash', 'jwt', 'token', 'env'} <= runtime.SECRET_KEYS
```

Also assert worker timeout is finite, canary port is 19002, redirect grace is exactly 300 seconds, status-token TTL is finite, and only panel service restart is allowlisted.

- [ ] **Step 2: Run complete backend + frontend + governance suite**

Run:
```bash
./.venv/bin/python -m unittest discover -s tests -v
bash -n scripts/*.sh install-local.sh
./.venv/bin/python -m compileall -q backend scripts
cd frontend && npm run lint && npm run build
node tests/panel-settings-smoke.mjs
node tests/responsive-smoke.mjs
```
Expected: all commands exit 0.

- [ ] **Step 3: Run dependency/static security and secret scans**

Use the exact CI commands from `.github/workflows/ci.yml` locally where available; run `git grep`/release sanitizer checks proving no `.env`, DB dump, key, certificate, plaintext password, staging job, or runtime state file can enter the public artifact.

- [ ] **Step 4: Bump version and write bilingual release docs**

Set all version-bearing files to `1.0.12`. Changelog/README/release notes must state: runtime main-admin username/password/path settings, current-password re-auth, generation-bound JWT invalidation, 5-minute old-path 307, detached canary/rollback worker, and explicit zero-change to OpenVPN/Node authentication/runtime.

Mark `PVN-032` implemented in the release branch only after automated tests pass; Production completion evidence is appended after live rollout.

- [ ] **Step 5: Commit release preparation**

```bash
git add VERSION backend/version.py frontend/package.json frontend/package-lock.json pyproject.toml manifest.json CHANGELOG.md README.md README.fa.md AGENTS.md ROADMAP.md docs/RELEASE-NOTES-v1.0.12.md docs/RELEASE-NOTES-v1.0.12.fa.md tests/test_panel_settings_production_contract.py
git commit -m "release: prepare v1.0.12 runtime admin settings"
```

### Task 8: Branch review, CI, safe Production rollout, and immutable GitHub Release

**Files/Systems:**
- Branch: `feat/pvn-032-panel-settings`
- Production: `/opt/pvnetwork-panel`, `pvnetwork-panel.service`, Nginx proxy to `127.0.0.1:19001`
- Safety evidence: normal OpenVPN service/config hash, Node PID, DB counts, public health/UI/assets.

- [ ] **Step 1: Fresh whole-branch review before merge**

Review diff from `723fbf6aec902b05374b70ab2a5dd01913cd0ba8` to branch head for secret persistence, command injection, path traversal, auth bypass, rollback correctness, TOTP migration, lock races, and forbidden service operations. Fix findings with tests before merge.

- [ ] **Step 2: Push branch, open PR, and require exact-head CI PASS**

Run `git push -u origin feat/pvn-032-panel-settings`; open PR to `main`; wait for security audit, unit/governance, Router OpenVPN real handshake, frontend build/runtime audit, browser matrix, JSON/secret guard, and lifecycle checks to pass.

- [ ] **Step 3: Create and verify Production rollback point before mutation**

Capture `/opt/pvnetwork-panel`, native PostgreSQL dump, `.env`, active Nginx site, IPv4/IPv6 firewall rules, `systemctl show` for panel/OpenVPN/Node services, current OpenVPN PID and SHA256 of `/etc/openvpn/server/server.conf`. Verify tar integrity and `pg_restore -l` before any file switch.

- [ ] **Step 4: Deploy exact merged tree to a 19002 canary first**

Build frontend with the live current path, start candidate code on `127.0.0.1:19002`, and verify `/healthz`, current panel HTML, referenced assets, login, Security Settings, panel-settings GET, and a synthetic candidate settings job in isolated staging mode. Do not perform a live username/password rotation during release verification unless the owner explicitly supplies replacement credentials.

- [ ] **Step 5: Cut public panel traffic to validated canary, update canonical tree, and return to 19001**

Temporarily point the active Nginx panel proxy at `127.0.0.1:19002`, run `nginx -t`, and use a graceful Nginx reload only for the release proxy cutover (never from the runtime-settings feature itself); sync exact merged tracked files into `/opt/pvnetwork-panel` while preserving `.env`, DB/data, `.venv`, node_modules and live dist until build completes, run migrations/generation bootstrap, build live frontend, restart only `pvnetwork-panel.service`, verify 19001, then point Nginx back to 19001 and retire canary.

- [ ] **Step 6: Verify zero VPN/Node interruption**

Compare before/after OpenVPN PID, Node PID, normal OpenVPN config SHA256, live listening ports, DB counts, `/healthz`, public UI/assets, and recent logs. Any OpenVPN/Node PID change attributable to rollout is a release blocker and requires investigation before tagging.

- [ ] **Step 7: Exercise live path transition only with an owner-approved target path**

When the owner provides the desired new path, use the UI itself: submit path-only change, confirm 307 from old path to new path with suffix preservation, verify authenticated Security Settings at the new path, wait until `redirect_expires_at`, then verify the old path returns 404. This step must not invent or silently change the owner's permanent path.

- [ ] **Step 8: Close ledger, tag, publish, and re-download verify**

After Production evidence is appended to `AGENTS.md`/`ROADMAP.md`, merge the docs closure commit, require final `main` CI PASS, create annotated tag `v1.0.12`, build sanitized source artifact plus `.sha256`, publish the GitHub Release, download both assets back, run `sha256sum -c`, inspect `VERSION=1.0.12`, and re-run the forbidden-private-file scan.
