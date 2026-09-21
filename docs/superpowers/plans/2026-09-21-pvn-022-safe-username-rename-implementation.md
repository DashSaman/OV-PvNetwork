# PVN-022 Safe Multi-Node Username Rename Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship `v1.0.16` with a durable, reversible username-rename workflow that preserves the user UUID/accounting/node assignments, stages the new OpenVPN identities on every assigned Node, cuts over atomically, revokes the old identities immediately, and never restarts the normal OpenVPN service.

**Architecture:** Add durable `user_rename_jobs` plus `user_lifecycle_locks` tables, a resumable rename engine, a short systemd-driven worker, and a narrow Node identity-inspection capability layered on top of the v1.0.15 per-user lifecycle primitives. The API queues jobs and returns immediately; the worker owns staged creation, pre-commit rollback, central DB cutover, post-commit revoke/cleanup, and retryable `cleanup_pending`. The frontend adds a dedicated Rename Username modal and polls sanitized job status while conflicting controls are disabled.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, PostgreSQL, Pydantic, Python asyncio/thread offload, requests, systemd, React/Vite, Axios, existing OpenVPN Node API and management-socket lifecycle helpers.

**Spec:** `docs/superpowers/specs/2026-09-21-pvn-022-safe-username-rename-design.md`

## Global Constraints

- Release target is exactly `v1.0.16`; PVN-022 is the only Production-visible feature in this patch.
- User UUID, owner, quota, expiry, usage/accounting records, AnyConnect UUID-bound credential, Router/MikroTik UUID/node credential identity, and explicit node assignments must remain unchanged.
- Old identity policy is option A: after successful cutover there is no grace period; old CN/profile is disabled/disconnected and then revoked/deleted immediately.
- Username remains read-only in ordinary Quick Edit; rename is a dedicated operation.
- Pre-commit failures restore the old identity and remove staged new identities; post-commit cleanup failures keep the new username authoritative and enter `cleanup_pending`.
- No per-user rename step may restart normal OpenVPN, Router compatibility OpenVPN, routing, firewall, Xray, or unrelated services.
- Job/status payloads must not contain certificates, private keys, passwords, Node API keys, or raw profile bytes.
- Existing API-token scope policy applies: `users:write` is required to start/retry rename; `users:read` is sufficient only for status reads. Interactive main-admin privilege must not be inferred merely from API-token authentication.
- Production rollout uses verified backup, canary `19002`, canonical `19001`, `pvnetwork-canary-retire-guard`, a synthetic identity only, artifact secret scan, SHA256, and public re-download verification.

## Review Focus

1. **Crash between disabling old CNs and central DB commit:** resume must inspect durable stage/evidence and restore old identities instead of guessing that cutover completed. Task 4 adds a restart-at-each-stage test.
2. **Two lifecycle mutations racing on the same UUID:** exactly one durable lifecycle lock may exist; delete/renew/status/node-update/ordinary edit must return 409 while rename owns the lock. Tasks 1 and 5 pin atomic lock behavior.
3. **Partial multi-node staging/cutover:** any failure before DB commit must remove every new staged identity and restore each old identity already disabled. Task 4 uses a three-node failure matrix.
4. **Prefix collisions (`ali` vs `ali2`) and stale CNs:** Node inspection/disable/revoke must use exact CN matching only. Task 2 adds exact-CN tests.
5. **Post-commit cleanup failure:** new username must stay committed, old identity must never be re-enabled automatically, and retry must be idempotent. Task 4 adds cleanup retry tests.

---

## File Map

**Create**
- `backend/alembic/versions/e7f8a9b0c1d2_user_rename_jobs.py` — durable rename jobs and per-user lifecycle locks.
- `backend/user_rename/contracts.py` — username normalization, state constants, sanitized job serialization.
- `backend/user_rename/repository.py` — atomic lock/job persistence helpers.
- `backend/user_rename/engine.py` — resumable stage machine and compensation logic.
- `backend/user_rename/worker.py` — process one runnable durable job at a time.
- `scripts/pvnetwork-user-rename-worker.py` — installed worker entrypoint.
- `ops/systemd/pvnetwork-user-rename-worker.service` — flocked oneshot worker.
- `ops/systemd/pvnetwork-user-rename-worker.timer` — low-latency durable polling.
- `frontend/src/components/RenameUserModal.jsx` — dedicated rename confirmation/progress UI.
- `frontend/src/components/RenameUserModal.css` — responsive modal/progress styling.
- `tests/test_user_rename_schema.py` — DB/job/lock invariants.
- `tests/test_user_rename_node_contract.py` — Node inspection and exact-CN contract.
- `tests/test_user_rename_engine.py` — stage machine, rollback, cleanup retry, preservation.
- `tests/test_user_rename_api.py` — auth, scope, IDOR, queue/status/retry behavior.
- `tests/test_user_rename_mutation_lock.py` — conflicting mutation blocking.
- `tests/test_user_rename_frontend.py` — static/UI contract and polling controls.
- `tests/test_user_rename_production_contract.py` — release/installer/runtime no-restart gates.

**Modify**
- `backend/db/models.py` — `UserRenameJob` and `UserLifecycleLock` models.
- `backend/schema/_input.py` — rename request model.
- `backend/node/requests.py` — sanitized Node identity-state request.
- `backend/node/assignment.py` — exact assigned-node snapshot helper for rename.
- `backend/routers/users.py` — queue/status/retry endpoints plus mutation lock checks.
- `scripts/node_patch.py` — Node identity-inspection helper/route and capability marker.
- `backend/node/deploy.py` — include PVN-022 Node capability during upgrades/new nodes.
- `scripts/install-runtime-tools.sh` — install worker and units.
- `scripts/pvnetwork-panel-smoke-test` — require rename worker timer/service and schema.
- `frontend/src/pages/UserManagement.jsx` — modal state, polling and conflict refresh.
- `frontend/src/components/UserTable.jsx` — Rename action and busy-state disabling.
- `frontend/src/lang/en.json`, `frontend/src/lang/fa.json` — user-facing rename copy.
- `backend/security_middleware.py` tests only unless scope classification proves incorrect; `/api/users/.../rename` must classify under `users`.
- `VERSION`, `CHANGELOG.md`, `README.md`, `README.fa.md`, `AGENTS.md`, `ROADMAP.md`, release notes — v1.0.16 metadata/evidence.

---

### Task 1: Durable Rename Job and Lifecycle Lock Schema

**Files:**
- Create: `backend/alembic/versions/e7f8a9b0c1d2_user_rename_jobs.py`
- Modify: `backend/db/models.py`
- Create: `backend/user_rename/contracts.py`
- Create: `backend/user_rename/repository.py`
- Test: `tests/test_user_rename_schema.py`

**Interfaces:**
- Produces: `UserRenameJob`, `UserLifecycleLock` SQLAlchemy models.
- Produces: `RenameState`, `normalize_rename_username(value: str) -> str`, `serialize_rename_job(job) -> dict`.
- Produces: `create_rename_job(...)`, `acquire_lifecycle_lock(...)`, `release_lifecycle_lock(...)`, `get_active_lock(...)`, `claim_runnable_job(...)`.
- Consumes later: every rename/API/worker task relies on these durable primitives.

- [ ] **Step 1: Write schema tests for immutable UUID linkage, unique lifecycle lock, states, and sanitized serialization**

```python
class UserRenameSchemaTests(unittest.TestCase):
    def test_normalize_username_uses_vpn_safe_contract(self):
        self.assertEqual(normalize_rename_username("new_user-2"), "new_user-2")
        for value in ("ab", "bad name", "bad/slash", "x" * 65):
            with self.assertRaises(ValueError):
                normalize_rename_username(value)

    def test_only_one_lifecycle_lock_exists_per_user_uuid(self):
        first = acquire_lifecycle_lock(self.db, "u-1", "rename", "job-1")
        self.assertEqual(first.user_uuid, "u-1")
        with self.assertRaises(LifecycleLocked):
            acquire_lifecycle_lock(self.db, "u-1", "delete", None)

    def test_status_payload_never_contains_node_secrets_or_profiles(self):
        payload = serialize_rename_job(self.job)
        self.assertNotIn("private_key", json.dumps(payload))
        self.assertNotIn("profile_bytes", json.dumps(payload))
        self.assertNotIn("api_key", json.dumps(payload))
```

- [ ] **Step 2: Run the focused tests and confirm RED**

Run: `PYTHONPATH=. .venv/bin/python -m unittest -v tests.test_user_rename_schema`
Expected: FAIL because the migration/models/contracts/repository do not exist.

- [ ] **Step 3: Add the Alembic migration and SQLAlchemy models**

Create tables with these durable fields:

```python
class UserRenameJob(Base):
    __tablename__ = "user_rename_jobs"
    id = mapped_column(String(36), primary_key=True)
    user_uuid = mapped_column(ForeignKey("users.uuid", ondelete="CASCADE"), nullable=False, index=True)
    old_name = mapped_column(String(64), nullable=False)
    new_name = mapped_column(String(64), nullable=False)
    state = mapped_column(String(32), nullable=False)
    actor = mapped_column(String(128), nullable=False)
    actor_type = mapped_column(String(32), nullable=False)
    snapshot_json = mapped_column(Text, nullable=False, default="{}")
    evidence_json = mapped_column(Text, nullable=False, default="{}")
    failure_reason = mapped_column(Text, nullable=True)
    created_at = mapped_column(BigInteger, nullable=False)
    updated_at = mapped_column(BigInteger, nullable=False)
    completed_at = mapped_column(BigInteger, nullable=True)

class UserLifecycleLock(Base):
    __tablename__ = "user_lifecycle_locks"
    user_uuid = mapped_column(ForeignKey("users.uuid", ondelete="CASCADE"), primary_key=True)
    operation = mapped_column(String(32), nullable=False)
    owner_token = mapped_column(String(64), nullable=False)
    job_id = mapped_column(String(36), nullable=True)
    acquired_at = mapped_column(BigInteger, nullable=False)
    expires_at = mapped_column(BigInteger, nullable=True)
```

Migration revision is `e7f8a9b0c1d2` with `down_revision = "d3e4f5a6b7c8"` (the current single Alembic head). It must add indexes on `user_rename_jobs(user_uuid, state)` and `user_rename_jobs(updated_at)` and a foreign key from `UserLifecycleLock.job_id` to `user_rename_jobs.id` with `SET NULL`.

- [ ] **Step 4: Implement contracts and repository atomicity**

`normalize_rename_username()` must enforce the existing safe subset `[A-Za-z0-9_-]{3,64}` without silently replacing characters during rename. `acquire_lifecycle_lock()` inserts and flushes under the table's unique PK, converting `IntegrityError` to `LifecycleLocked`. Rename-owned locks have `expires_at=None`; short transient mutation locks may have an explicit expiry but rename locks are never timeout-unlocked.

- [ ] **Step 5: Run focused tests and migration upgrade/downgrade in a temporary database**

Run:
```bash
PYTHONPATH=. .venv/bin/python -m unittest -v tests.test_user_rename_schema
(cd backend && ../.venv/bin/alembic -c alembic.ini upgrade head)
(cd backend && ../.venv/bin/alembic -c alembic.ini current)
```
Expected: PASS and exactly one Alembic head.

- [ ] **Step 6: Commit Task 1**

```bash
git add backend/db/models.py backend/alembic/versions/e7f8a9b0c1d2_user_rename_jobs.py backend/user_rename tests/test_user_rename_schema.py
git commit -m "feat: add durable user rename jobs and locks"
```

---

### Task 2: Node Identity Inspection Capability

**Files:**
- Modify: `scripts/node_patch.py`
- Modify: `backend/node/deploy.py`
- Modify: `backend/node/requests.py`
- Test: `tests/test_user_rename_node_contract.py`
- Test: `tests/test_node_user_lifecycle_no_restart.py`

**Interfaces:**
- Produces Node endpoint: `GET /sync/user/{client_name}/identity`.
- Produces central client method: `NodeRequests.get_user_identity(name: str) -> dict`.
- Identity payload: `{exists, valid_certificate, profile_exists, ccd_enabled, connected, client_name, capability_version}` only.
- Must not expose certificate contents, profile bytes, keys, filesystem paths, or Node secrets.

- [ ] **Step 1: Write RED tests for exact-CN identity inspection and no-restart behavior**

```python
def test_identity_inspection_is_exact_cn_only(self):
    state = inspect_user_identity("ali-NodeA")
    self.assertEqual(state["client_name"], "ali-NodeA")
    self.assertFalse(state["connected"] when self.status_contains_only("ali2-NodeA") else False)

def test_identity_payload_is_sanitized(self):
    payload = self.client.get_user_identity("ali-NodeA")
    self.assertNotIn("private", json.dumps(payload).lower())
    self.assertNotIn("key", payload)
    self.assertNotIn("profile", {k for k in payload if k != "profile_exists"})
```

Also assert the patched lifecycle/inspection source contains no `systemctl restart openvpn` call.

- [ ] **Step 2: Run Node contract tests and confirm RED**

Run: `PYTHONPATH=. .venv/bin/python -m unittest -v tests.test_user_rename_node_contract`
Expected: FAIL because identity inspection is absent.

- [ ] **Step 3: Add self-contained Node identity helper and route**

The helper must inspect only exact leaf artifacts and exact `CLIENT_LIST` Common Names:

```python
def get_user_identity_state(name: str) -> dict:
    name = str(name or "").strip()
    if not _pvnetwork_safe_name(name):
        return {"exists": False, "client_name": name, "error": "invalid_name"}
    valid_certificate = _pvnetwork_valid_cert_exists(name)
    profile_exists = os.path.isfile(f"/root/{name}.ovpn")
    ccd_enabled = any(os.path.isfile(os.path.join(path, name)) for path in _pvnetwork_ccd_dirs())
    connected = _pvnetwork_exact_cn_connected(name)
    return {
        "exists": bool(valid_certificate or profile_exists),
        "valid_certificate": bool(valid_certificate),
        "profile_exists": bool(profile_exists),
        "ccd_enabled": bool(ccd_enabled),
        "connected": bool(connected),
        "client_name": name,
        "capability_version": "pvn-user-identity-v1",
    }
```

Add `@router.get("/user/{name}/identity")` in the patched Node sync router and keep all existing routes backward compatible.

- [ ] **Step 4: Add `NodeRequests.get_user_identity` with strict timeouts and schema normalization**

Return `{}` on transport/protocol failure and normalize booleans/client name rather than returning arbitrary Node JSON.

- [ ] **Step 5: Verify Node patch idempotency and legacy-node upgrade path**

Run:
```bash
PYTHONPATH=. .venv/bin/python -m unittest -v tests.test_user_rename_node_contract tests.test_node_user_lifecycle_no_restart
python3 scripts/node_patch.py --help
```
Expected: PASS; running the patch twice against a fixture produces identical output.

- [ ] **Step 6: Commit Task 2**

```bash
git add scripts/node_patch.py backend/node/deploy.py backend/node/requests.py tests/test_user_rename_node_contract.py tests/test_node_user_lifecycle_no_restart.py
git commit -m "feat: add node identity inspection for safe rename"
```

---

### Task 3: Assigned-Node Snapshot and Rename Stage Primitives

**Files:**
- Modify: `backend/node/assignment.py`
- Create: `backend/user_rename/engine.py`
- Test: `tests/test_user_rename_engine.py`

**Interfaces:**
- Produces: `snapshot_assigned_nodes(db, user_uuid) -> list[AssignedRenameNode]`.
- Produces engine primitives: `preflight_job`, `stage_new_identities`, `disable_old_identities`, `rollback_precommit`, `revoke_old_identities`.
- Node evidence stored by node ID contains only names, booleans and timestamps.

- [ ] **Step 1: Write RED tests for one-node/multi-node preflight and staging rollback**

```python
async def test_staging_failure_deletes_every_new_identity_created_by_job(self):
    nodes = [self.node(1, "A"), self.node(2, "B"), self.node(3, "C")]
    self.fake[1].create_ok = True
    self.fake[2].create_ok = True
    self.fake[3].create_ok = False
    with self.assertRaises(RenameStageError):
        await stage_new_identities(self.job, self.db)
    self.assertEqual(self.fake[1].deleted, ["new-A"])
    self.assertEqual(self.fake[2].deleted, ["new-B"])
    self.assertEqual(self.user.name, "old")
```

Add inactive-user staging coverage: new identities are created then immediately deactivated and remain inactive.

- [ ] **Step 2: Run focused engine tests and confirm RED**

Run: `PYTHONPATH=. .venv/bin/python -m unittest -v tests.test_user_rename_engine.UserRenameStageTests`
Expected: FAIL because engine primitives do not exist.

- [ ] **Step 3: Implement preflight and staging**

Preflight must snapshot ordered assigned Node IDs/names, original active state and central immutable values, require every assigned Node to be reachable/capable, and reject if the new CN unexpectedly already exists. Staging creates each `<new>-<node>` identity, verifies identity state plus OVPN download success, deactivates it if original user is inactive, and records `staged_node_ids` durably after each success.

- [ ] **Step 4: Implement reversible old-identity disable gate**

For each old CN, call `change_user_status(..., False)`, inspect until `connected=False`, and durably append `disabled_old_node_ids`. Do not revoke in this phase.

- [ ] **Step 5: Implement idempotent pre-commit rollback**

Rollback must:
1. re-enable only old identities that this job disabled and only when original user was active;
2. delete every new identity staged by this job;
3. preserve original inactive state when user was inactive;
4. write `rolled_back` only after all compensation attempts finish; otherwise write `failed` with sanitized node IDs needing operator recovery.

- [ ] **Step 6: Run focused stage/rollback matrix**

Run: `PYTHONPATH=. .venv/bin/python -m unittest -v tests.test_user_rename_engine.UserRenameStageTests`
Expected: PASS for one-node, three-node, inactive-user, stage-node-2 failure and disable-node-2 failure cases.

- [ ] **Step 7: Commit Task 3**

```bash
git add backend/node/assignment.py backend/user_rename/engine.py tests/test_user_rename_engine.py
git commit -m "feat: stage and roll back multi-node rename identities"
```

---

### Task 4: Atomic Central Cutover, Post-Commit Revoke and Resume Semantics

**Files:**
- Modify: `backend/user_rename/engine.py`
- Modify: `backend/user_rename/repository.py`
- Test: `tests/test_user_rename_engine.py`
- Test: `tests/test_router_openvpn_user_lifecycle.py`

**Interfaces:**
- Produces: `commit_central_rename(job_id, db) -> None`.
- Produces: `run_rename_job(job_id: str) -> str` returning terminal/current state.
- Produces: `retry_cleanup(job_id: str) -> str`.

- [ ] **Step 1: Write RED preservation tests around DB cutover**

Capture before/after values for `uuid`, `owner`, `total`, `used`, `expiry_date`, `device_limit`, `UserNode`, `UserNodeUsage`, `AnyConnectCredential`, and `RouterOpenVpnCredential`. Assert only `User.name` changes.

```python
self.assertEqual(before.uuid, after.uuid)
self.assertEqual(before.node_ids, after.node_ids)
self.assertEqual(before.usage_rows, after.usage_rows)
self.assertEqual(before.router_usernames, after.router_usernames)
self.assertEqual(before.anyconnect_hash, after.anyconnect_hash)
self.assertEqual(after.name, "newname")
```

Also assert active-session rows belonging to old CN are gone after the old disconnect/cutover gate, while historical UUID-keyed usage/domain records remain.

- [ ] **Step 2: Write RED restart/resume matrix**

Persist a job at each stage (`preflight`, `staging`, `rolling_back`, `cutover`, `revoking_old`, `cleanup_pending`) and call `run_rename_job()` again. Expected behavior must be idempotent and stage-aware; `rolling_back` resumes compensation before any forward work, never repeat DB rename after it is already committed, and never re-enable old identity from `cleanup_pending`.

- [ ] **Step 3: Implement the single DB transaction for central rename**

Within one transaction:
- re-select user by UUID and confirm `name == job.old_name`;
- reject if another user owns `job.new_name`;
- set `User.name = job.new_name`;
- preserve all UUID-keyed rows untouched;
- delete stale `ActiveSession` rows whose `user_uuid` is the target and `common_name` is one of this job's old CNs;

Do not rewrite Router credentials or AnyConnect credential rows because they are UUID-bound. Append durable structured rename audit evidence containing `old_name`, `new_name`, `actor`, `actor_type`, `job_id`, `cutover_at` and terminal timestamp; historical immutable request/audit rows are not rewritten.

- [ ] **Step 4: Implement post-commit revoke/delete with cleanup_pending**

After DB commit, delete/revoke each old CN through the v1.0.15 lifecycle path and verify `valid_certificate=False`, `connected=False`, and old profile unavailable. On any Node failure, keep new name committed, set `cleanup_pending`, retain the durable lifecycle lock, and record only sanitized failed Node IDs.

- [ ] **Step 5: Implement cleanup retry and terminal lock release**

`retry_cleanup()` operates only on `cleanup_pending`; it retries failed old identities, verifies all old identities absent/revoked, then sets `completed`, `completed_at`, and releases the lifecycle lock. A completed job called again returns completed without side effects.

- [ ] **Step 6: Run engine + Router/AnyConnect preservation tests**

Add an AnyConnect regression in the same focused gate: after central cutover, authentication lookup by the new username resolves the same UUID-bound credential; the old username no longer resolves that user.

Run:
```bash
PYTHONPATH=. .venv/bin/python -m unittest -v tests.test_user_rename_engine tests.test_router_openvpn_user_lifecycle
```
Expected: PASS, including post-commit failure where old access never comes back.

- [ ] **Step 7: Commit Task 4**

```bash
git add backend/user_rename/engine.py backend/user_rename/repository.py tests/test_user_rename_engine.py tests/test_router_openvpn_user_lifecycle.py
git commit -m "feat: add atomic rename cutover and cleanup recovery"
```

---

### Task 5: Guard All Conflicting User Lifecycle Mutations

**Files:**
- Modify: `backend/user_rename/repository.py`
- Modify: `backend/routers/users.py`
- Test: `tests/test_user_rename_mutation_lock.py`
- Test: existing renewal/node-assignment/status/delete tests as applicable.

**Interfaces:**
- Produces: `transient_user_mutation_lock(db, user_uuid, operation)` context manager.
- Rename queue owns a non-expiring durable lock from queue time through completion/rolled_back.
- Conflicting mutation response: HTTP 409 with sanitized `{operation, job_id}` only for authenticated authorized callers.

- [ ] **Step 1: Write RED conflict tests for every required mutation**

With a rename lock present, assert 409 for:
- `PUT /api/users/{uuid}` ordinary edit;
- reset usage route used by the current UI;
- `POST /api/users/{uuid}/renew`;
- `PUT /api/users/{uuid}/nodes`;
- `PUT /api/users/{uuid}/status`;
- `DELETE /api/users/{uuid}`;
- second `POST /api/users/{uuid}/rename`.

Also test a transient delete lock makes rename queue return 409 rather than racing.

- [ ] **Step 2: Run lock tests and confirm RED**

Run: `PYTHONPATH=. .venv/bin/python -m unittest -v tests.test_user_rename_mutation_lock`
Expected: FAIL because existing routes ignore lifecycle locks.

- [ ] **Step 3: Implement transient lock context**

Use the same unique `user_uuid` row. Normal mutations get an `owner_token`, operation name, and bounded `expires_at`; release in `finally`. Only expired **transient** locks (`job_id IS NULL`) may be reclaimed. Rename locks (`job_id IS NOT NULL`) are never silently expired.

- [ ] **Step 4: Wrap all conflicting routes without changing existing business semantics**

Acquire the transient lock only after authorization/target lookup and before local or remote mutation. Keep existing error codes/policies for quota/ownership checks. Always release in `finally`, including remote Node failure.

- [ ] **Step 5: Run mutation regression suites**

Run:
```bash
PYTHONPATH=. .venv/bin/python -m unittest -v \
  tests.test_user_rename_mutation_lock \
  tests.test_user_renewal \
  tests.test_user_node_assignment \
  tests.test_node_user_lifecycle_no_restart
```
Expected: PASS.

- [ ] **Step 6: Commit Task 5**

```bash
git add backend/user_rename/repository.py backend/routers/users.py tests/test_user_rename_mutation_lock.py
git commit -m "feat: serialize user lifecycle mutations during rename"
```

---

### Task 6: Rename API, Authorization and Durable Worker

**Files:**
- Modify: `backend/schema/_input.py`
- Modify: `backend/routers/users.py`
- Create: `backend/user_rename/worker.py`
- Create: `scripts/pvnetwork-user-rename-worker.py`
- Create: `ops/systemd/pvnetwork-user-rename-worker.service`
- Create: `ops/systemd/pvnetwork-user-rename-worker.timer`
- Modify: `scripts/install-runtime-tools.sh`
- Test: `tests/test_user_rename_api.py`
- Test: `tests/test_security_scope_regression.py`

**Interfaces:**
- `POST /api/users/{uuid}/rename` body `{ "new_username": "..." }` -> HTTP 202 with sanitized job data.
- `GET /api/users/rename/active` -> all non-terminal rename jobs visible to the current actor, sanitized and ownership-filtered; this lets the UI recover after reload without remembering a local job ID.
- `GET /api/users/{uuid}/rename/{job_id}` -> current sanitized status.
- `POST /api/users/{uuid}/rename/{job_id}/retry` -> HTTP 202 only for retryable `cleanup_pending`/recoverable states.
- Worker command: `/usr/local/sbin/pvnetwork-user-rename-worker.py --once`.

- [ ] **Step 1: Write RED API auth/scope/IDOR tests**

Test matrix:
- main admin can rename any user;
- delegated admin can rename only own user;
- delegated admin receives 404/403 according to existing ownership convention for another reseller's user;
- API token with `users:write` may queue/retry;
- API token with only `users:read` may read status but gets 403 on queue/retry;
- unrelated/invalid job ID does not leak another user's old/new names;
- `GET /api/users/rename/active` returns only jobs the actor is authorized to view and requires `users:read`.

- [ ] **Step 2: Write RED queue tests**

Assert the POST endpoint validates collision/no-op/format, atomically creates job + durable rename lock, commits before returning, never performs Node network I/O inline, and returns 202.

- [ ] **Step 3: Implement request model and endpoints**

```python
class RenameUserRequest(BaseModel):
    new_username: str = Field(min_length=3, max_length=64)
```

Queue path must call `normalize_rename_username`, authorize with `_owned_user_or_404`, check `crud.get_user_by_name`, create job+lock atomically and return `serialize_rename_job(job)`. The active-jobs route must ownership-filter in SQL/Python before serialization and must never expose jobs for users outside a delegated admin's ownership.

- [ ] **Step 4: Implement worker claiming semantics**

`run_once()` selects the oldest runnable non-terminal job using `SELECT ... FOR UPDATE SKIP LOCKED`, marks `updated_at`, commits the claim, then calls `run_rename_job(job.id)`. One failed job must not block unrelated users.

- [ ] **Step 5: Add systemd units and installer**

Service:
```ini
[Service]
Type=oneshot
WorkingDirectory=/opt/pvnetwork-panel
Environment=PYTHONPATH=/opt/pvnetwork-panel
ExecStart=/usr/bin/flock -n /run/pvnetwork-user-rename-worker.lock /opt/pvnetwork-panel/.venv/bin/python3 /usr/local/sbin/pvnetwork-user-rename-worker.py --once
TimeoutStartSec=10min
```

Timer uses `OnBootSec=30s`, `OnUnitInactiveSec=3s`, `Persistent=true`, and is enabled by Production rollout after migration.

- [ ] **Step 6: Run API/security/worker tests**

Run:
```bash
PYTHONPATH=. .venv/bin/python -m unittest -v tests.test_user_rename_api tests.test_security_scope_regression
python3 -m py_compile backend/user_rename/worker.py scripts/pvnetwork-user-rename-worker.py
```
Expected: PASS and API-token scope classifier recognizes rename under `users`.

- [ ] **Step 7: Commit Task 6**

```bash
git add backend/schema/_input.py backend/routers/users.py backend/user_rename/worker.py scripts/pvnetwork-user-rename-worker.py ops/systemd/pvnetwork-user-rename-worker.* scripts/install-runtime-tools.sh tests/test_user_rename_api.py tests/test_security_scope_regression.py
git commit -m "feat: expose durable user rename API and worker"
```

---

### Task 7: Rename Username UI and Conflict UX

**Files:**
- Create: `frontend/src/components/RenameUserModal.jsx`
- Create: `frontend/src/components/RenameUserModal.css`
- Modify: `frontend/src/pages/UserManagement.jsx`
- Modify: `frontend/src/components/UserTable.jsx`
- Modify: `frontend/src/lang/en.json`
- Modify: `frontend/src/lang/fa.json`
- Test: `tests/test_user_rename_frontend.py`
- Keep: `frontend/src/components/InlineUserQuickEdit.jsx` username read-only.

**Interfaces:**
- `RenameUserModal` props: `{ user, nodes, open, onClose, onCompleted }`.
- Poll status endpoint every 1s while state is non-terminal; stop timer on close/unmount/terminal state.
- `UserTable` receives `onRename` and `busyUserUuids`.

- [ ] **Step 1: Write RED frontend contract tests**

Assert:
- Quick Edit still renders read-only username and migration hint;
- Actions dropdown contains `Rename Username`;
- modal shows current name, assigned nodes, old-profile invalidation warning and active-session disconnect warning;
- submit posts only `{new_username}` to dedicated endpoint;
- progress labels cover `preflight`, `staging`, `cutover`, `revoking_old`, `cleanup_pending`, `completed`;
- destructive actions for the busy UUID are disabled while rename is non-terminal;
- polling cleanup runs on unmount.

- [ ] **Step 2: Run frontend contract tests and confirm RED**

Run: `PYTHONPATH=. .venv/bin/python -m unittest -v tests.test_user_rename_frontend`
Expected: FAIL because modal/action/polling do not exist.

- [ ] **Step 3: Implement Rename modal**

The modal must not contain profile/key material. It displays sanitized node names/IDs from the user/node lists and server job payload, disables submit for same name/invalid local format, and requires an explicit confirmation checkbox acknowledging old profiles stop working.

- [ ] **Step 4: Wire UserManagement polling and table busy state**

On initial page load call `/users/rename/active` and rebuild the busy-job map so a browser refresh does not lose progress. On queue success store `{uuid: jobId}`. Poll `/users/${uuid}/rename/${jobId}` every 1000ms. On `completed`, stop polling, close modal, `fetchUsers()` and leave existing subscription UUID link unchanged. On `cleanup_pending`, keep modal visible with retry action; do not present the rename as rolled back.

- [ ] **Step 5: Add English/Persian strings and responsive CSS**

Include explicit copy for no-grace revocation and session disconnect. Keep buttons touch-safe and modal internally scrollable on short/mobile viewports.

- [ ] **Step 6: Run frontend lint/build and UI contract tests**

Run:
```bash
PYTHONPATH=. .venv/bin/python -m unittest -v tests.test_user_rename_frontend tests.test_inline_user_quick_edit
cd frontend && npm run lint && npm run build
```
Expected: PASS.

- [ ] **Step 7: Commit Task 7**

```bash
git add frontend/src/components/RenameUserModal.jsx frontend/src/components/RenameUserModal.css frontend/src/pages/UserManagement.jsx frontend/src/components/UserTable.jsx frontend/src/lang/en.json frontend/src/lang/fa.json tests/test_user_rename_frontend.py
git commit -m "feat: add safe username rename workflow to users UI"
```

---

### Task 8: Production/Installer Contract, Full Regression and Release Metadata

**Files:**
- Modify: `scripts/pvnetwork-panel-smoke-test`
- Create/Modify: `tests/test_user_rename_production_contract.py`
- Modify: `VERSION`
- Modify: `CHANGELOG.md`
- Modify: `README.md`
- Modify: `README.fa.md`
- Modify: `AGENTS.md`
- Modify: `ROADMAP.md`
- Create: `docs/RELEASE-NOTES-v1.0.16.md`
- Create: `docs/RELEASE-NOTES-v1.0.16.fa.md`

**Interfaces:**
- Production smoke requires Alembic at head, worker timer active, worker entrypoint installed, panel API route present, and no unexpected OpenVPN restart policy in rename code.
- Version is exactly `1.0.16` everywhere release metadata requires it.

- [ ] **Step 1: Add RED production contract tests**

Pin that:
- installer includes worker script + units;
- smoke requires `pvnetwork-user-rename-worker.timer` active;
- rename source contains no `systemctl restart openvpn` or `restart_openvpn_service` call;
- release version references are `1.0.16`;
- README/FA release delta explains that old profiles are immediately invalidated after successful rename.

- [ ] **Step 2: Run production contract tests and confirm RED**

Run: `PYTHONPATH=. .venv/bin/python -m unittest -v tests.test_user_rename_production_contract`
Expected: FAIL until smoke/version/docs are updated.

- [ ] **Step 3: Update smoke/install/release documentation**

`pvnetwork-panel-smoke-test` must check service/timer files and API schema without causing mutations. Release notes explicitly state UUID/accounting/node-assignment preservation, no grace period, no OpenVPN restart, rollback semantics and cleanup_pending semantics.

- [ ] **Step 4: Run exact-head local release gate**

Run:
```bash
PYTHONPATH=. .venv/bin/python -m unittest discover -v tests
python3 -m compileall -q backend scripts
bash -n scripts/install-runtime-tools.sh scripts/pvnetwork-panel-smoke-test
cd frontend && npm run lint && npm run build && npm audit --audit-level=high
```
Expected: all Python/governance tests PASS, syntax PASS, frontend lint/build PASS, high/critical npm audit findings = 0.

- [ ] **Step 5: Run secret/private-material and diff review**

Use the repository's existing release guard. Verify staged files contain no `.env`, DB dump, OVPN profile, PEM/key material, credentials, customer hostnames/IPs or synthetic private keys. Review `git diff v1.0.15...HEAD` and confirm PVN-022 is the only Production-visible feature.

- [ ] **Step 6: Commit Task 8**

```bash
git add scripts/pvnetwork-panel-smoke-test tests/test_user_rename_production_contract.py VERSION CHANGELOG.md README.md README.fa.md AGENTS.md ROADMAP.md docs/RELEASE-NOTES-v1.0.16.md docs/RELEASE-NOTES-v1.0.16.fa.md
git commit -m "docs: prepare v1.0.16 safe username rename release"
```

---

### Task 9: Whole-Branch Review, PR and CI

**Files:**
- Review all PVN-022 changes; no new feature files unless review finds a reproducible defect.

**Interfaces:**
- Produces one exact-head PR and one merged-main CI result used as Production gate.

- [ ] **Step 1: Self-review against the approved spec**

Check every success/failure condition from Sections 5-13 of the spec. Explicitly verify that no code path can re-enable the old identity after central commit.

- [ ] **Step 2: Re-run focused rename suites**

Run:
```bash
PYTHONPATH=. .venv/bin/python -m unittest -v \
  tests.test_user_rename_schema \
  tests.test_user_rename_node_contract \
  tests.test_user_rename_engine \
  tests.test_user_rename_mutation_lock \
  tests.test_user_rename_api \
  tests.test_user_rename_frontend \
  tests.test_user_rename_production_contract
```
Expected: PASS.

- [ ] **Step 3: Push feature branch and open PR to `main`**

Record exact head SHA. Do not deploy from the feature branch.

- [ ] **Step 4: Wait for exact-head PR CI and inspect every blocking step**

Required green gates include dependency/static security audit, Python/governance tests, security regression suite, Router/OpenVPN safety contracts, real dual-auth handshake, frontend production build/audit, browser matrix, secret/private-material guard and installer references.

- [ ] **Step 5: Merge only the exact reviewed head and wait for push-triggered `main` CI**

If the PR head changes, discard the old CI as a gate and run CI on the new exact head. Production may start only when merged-main CI is SUCCESS.

---

### Task 10: Production Canary, Synthetic Rename and Immutable v1.0.16 Release

**Files:**
- Production runtime only after Task 9 gates pass.
- Closure evidence updates to `AGENTS.md`, `ROADMAP.md`, and release notes require a docs-only follow-up PR before immutable tagging if evidence differs from pre-release assumptions.

**Interfaces:**
- Production synthetic user is disposable and contains no customer data.
- Success evidence must prove old profile invalid, new profile valid, UUID/assignments/accounting preserved, normal OpenVPN PID/config hash unchanged.

- [ ] **Step 1: Capture rollback point and immutable baseline**

Record:
- source backup + SHA256;
- PostgreSQL dump + `pg_restore -l` verification;
- `.env` backup + SHA256 without printing secrets;
- panel, Node and normal OpenVPN PIDs;
- normal `/etc/openvpn/server/server.conf` SHA256;
- Router compatibility config hash;
- current DB counts and Alembic revision.

No cutover if any backup verification fails.

- [ ] **Step 2: Start candidate panel on `19002` from exact merged `main`**

Apply migration to the controlled candidate/Production DB only after backup. Build frontend with current path, start canary with isolated runtime state where applicable, verify `/healthz` reports `1.0.16`, panel/users/assets return 200, and authenticated rename OpenAPI/routes exist.

- [ ] **Step 3: Upgrade required Node capability only**

Patch identity inspection/lifecycle capability on the designated Production Node(s), compile-check Node modules, restart only `ov-node.service` if required, and prove normal OpenVPN PID/config hash did not change.

- [ ] **Step 4: Cut public panel traffic to canary and update canonical `19001`**

Follow the existing fail-closed procedure. After canonical reports `1.0.16`, restore Nginx config to `19001` on disk and run `pvnetwork-canary-retire-guard`; stop canary only after `CANARY_RETIRE_SAFE=YES` and cache-busted public health is 200/1.0.16.

- [ ] **Step 5: Create a dedicated synthetic multi-node user**

Use a unique sanitized username and at least two assigned Nodes when Production safely has two suitable Nodes; otherwise one assigned test Node plus the full multi-node behavior remains CI-proven. Record UUID, owner/quota/expiry/used/device-limit/assignments in a private evidence file, not release notes.

- [ ] **Step 6: Execute the real Rename Username API and watch durable stages**

Queue `old -> new`, observe `queued -> preflight -> staging -> cutover -> revoking_old -> completed`. Capture only sanitized job/node IDs and timestamps. If `cleanup_pending` occurs, do not tag; exercise retry until completed or roll back the release if a blocking defect is found.

- [ ] **Step 7: Verify identity and preservation gates**

Prove:
- same user UUID before/after;
- same owner/quota/expiry/used/device-limit and node assignment rows;
- Router credential rows unchanged;
- AnyConnect UUID-bound credential hash/state unchanged;
- old CN disconnected and old OVPN profile authentication/retrieval fails;
- new profile retrieval succeeds and new CN can authenticate;
- normal OpenVPN PID and server-config hash unchanged across rename;
- no 5xx and public `/healthz`, panel root and `/users` remain 200.

- [ ] **Step 8: Delete the synthetic test user through normal safe lifecycle and verify cleanup**

Do not leave test identities/certificates/jobs/locks active. Historical completed job/audit evidence may remain if sanitized by normal retention policy.

- [ ] **Step 9: Record Production evidence through a docs-only closure PR**

Update `AGENTS.md`, `ROADMAP.md`, release notes with sanitized exact CI SHAs/runs, backup/canary/rename evidence and any non-secret operational observation. Run exact-head docs CI and merged-main CI before tagging.

- [ ] **Step 10: Build and verify sanitized release artifact**

Build `pvnetwork-panel-v1.0.16.tar.gz` from the exact final main/tag candidate. Verify `VERSION=1.0.16`, run private-material/secret scan, list archive entries, and create SHA256.

- [ ] **Step 11: Tag and publish immutable release**

Create `v1.0.16` exactly on final green `main`, publish English/Persian release notes and upload artifact + `.sha256`.

- [ ] **Step 12: Re-download from GitHub and verify independently**

Download both assets from the public Release URL, verify SHA256, archive entry count, `VERSION=1.0.16`, and repeat the private-material scan on the downloaded archive. Only then mark PVN-022 `[x] RELEASED`.

---

## Final Acceptance Checklist

- [ ] Rename is a dedicated UUID-scoped job, not a normal edit-field mutation.
- [ ] Job/lock state survives panel/worker restarts.
- [ ] All assigned Nodes stage and verify the new identity before old identity changes.
- [ ] Pre-commit failure restores old state and removes staged new state.
- [ ] Central username cutover is atomic and UUID-keyed accounting/assignment/credentials are preserved.
- [ ] Old CN/profile is immediately disabled/disconnected and revoked/deleted after commit; no grace period exists.
- [ ] `cleanup_pending` never re-enables old identity and is retryable/idempotent.
- [ ] Conflicting lifecycle operations serialize with rename.
- [ ] API authorization, delegated ownership, IDOR and API-token scope tests pass.
- [ ] Quick Edit username remains read-only; dedicated modal shows warnings/progress/retry.
- [ ] Exact-CN handling prevents `ali` operations from affecting `ali2`.
- [ ] Normal OpenVPN service PID/config remain unchanged during Production synthetic rename.
- [ ] Full CI, Production canary/guard, docs closure, artifact scan, SHA and public re-download verification all pass.
