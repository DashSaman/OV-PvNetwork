# PVNetwork Ownership + PostgreSQL-First Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship PVN-025/v1.0.4 with zero legacy OV naming in current source/runtime, then PVN-026/v1.0.5 with PostgreSQL as the required Production database and canonical `pvnetwork_panel` database/role.

**Architecture:** Work only in an isolated Git worktree. PVN-025 introduces a canonical-name contract and migrates Production via parallel runtime/service cutover; PVN-026 introduces an explicit database-mode contract and migrates between PostgreSQL databases using verified dump/restore and canary validation. Production mutations remain serialized and rollback-first.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2, Alembic, PostgreSQL/psycopg3, React/Vite, systemd, nginx, Bash, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-19-pvnetwork-ownership-postgresql-design.md`

## Global Constraints

- Current tracked source must contain zero case-insensitive `ov-panel`, `ov_panel`, `ovpanel`, `OV-Panel`, `OVPanel`, or `ovpv` after PVN-025.
- Canonical root `/opt/pvnetwork-panel`; service `pvnetwork-panel.service`; config `/etc/pvnetwork`; CLI `pvnetwork`; frontend key `pvnetwork_language`.
- Production-visible work requires verified backup, rollback path, local/public health, changed-workflow verification, and AGENTS evidence before `[x]`.
- Do not change firewall, routing, tunnels, node certificates, customer credentials, or unrelated services.
- Historical tags/releases remain immutable.
- PostgreSQL is mandatory in Production after PVN-026; SQLite remains explicit test/dev only.
- Old Production runtime/database remain available through the rollback window; do not drop them in the same change window.

## Review Focus

- Legacy-token false negatives: mixed case, separators, filenames, service/config strings must still fail the source gate.
- Fresh install without `DATABASE_URL`: Production setup must provision/validate PostgreSQL instead of silently creating SQLite.
- Upgrade from the current live root/service: preserved `.env`, assets, systemd drop-ins and nginx path must not be lost.
- PostgreSQL cutover under live Mirza traffic: row parity and writes after cutover must be verified before old DB is retired.
- Rollback after partial cutover: nginx/service/database URL must each have a deterministic reverse step.

---
### Task 1: Canonical ownership contract and failing legacy-name gate

**Files:**
- Create: `tests/test_pvnetwork_ownership.py`
- Modify: `AGENTS.md`, `.github/workflows/ci.yml`

**Interfaces:**
- Produces: a reusable tracked-source scanner and canonical constants asserted by CI.
- Consumes: the forbidden token set and canonical names from the spec.

- [ ] **Step 1: Write RED tests** asserting canonical root/service/config/CLI/storage names and scanning tracked files for forbidden legacy tokens, with a fixture proving each forbidden spelling is detected.
- [ ] **Step 2: Run** `python3 -m unittest tests.test_pvnetwork_ownership -v`; expected FAIL because legacy strings remain and PVN-025 is not registered.
- [ ] **Step 3: Register** `PVN-025 [~]` target `v1.0.4` in `AGENTS.md` and add the scanner invocation to CI without weakening existing secret guards.
- [ ] **Step 4: Run the focused test**; expected to keep failing only on real legacy occurrences, proving the gate is wired correctly.
- [ ] **Step 5: Commit** `test: enforce PVNetwork ownership namespace`.

### Task 2: Installer, lifecycle, service and runtime namespace rebrand

**Files:**
- Modify: `installer.py`, `install-local.sh`, `scripts/manage.sh`, `scripts/healthcheck.sh`, `scripts/configure_env.py`, `scripts/verify.sh`, `scripts/export-production.sh`
- Test: `tests/test_pvnetwork_ownership.py`, new `tests/test_runtime_namespace.py`

**Interfaces:**
- Produces: `/opt/pvnetwork-panel`, `pvnetwork-panel.service`, `/etc/pvnetwork`, `pvnetwork` CLI and canonical backup names.
- Consumes: ownership constants from Task 1.

- [ ] **Step 1: Write RED runtime tests** that inspect generated installer/service/lifecycle content and reject legacy paths/service/CLI identifiers.
- [ ] **Step 2: Run focused tests**; expected FAIL on current installer/runtime scripts.
- [ ] **Step 3: Replace runtime defaults** with canonical PVNetwork names while preserving environment overrides needed for disposable testing.
- [ ] **Step 4: Add explicit migration-safe behavior**: fresh install refuses an occupied canonical root; update/backup/rollback operate only on the canonical root; service restart targets only `pvnetwork-panel.service`.
- [ ] **Step 5: Run** shell syntax, focused tests, and installer dry-run/reference checks; expected PASS.
- [ ] **Step 6: Commit** `refactor: move runtime namespace to PVNetwork`.

### Task 3: Backend/frontend/package namespace cleanup

**Files:**
- Modify: `backend/**`, `frontend/src/**`, `frontend/tests/**`, `pyproject.toml`, `manifest.json`, `package-lock.json`, `.env.example`, `backend/alembic.ini`
- Test: `tests/test_pvnetwork_ownership.py`, existing unit/browser suites

**Interfaces:**
- Produces: canonical backend paths/defaults, `pvnetwork_language`, PVNetwork backup/archive metadata and package identifiers.
- Consumes: runtime namespace from Task 2.

- [ ] **Step 1: Extend RED tests** for backup filename/format identifiers, frontend language storage key, backend default tunnel/domain placeholders, app metadata and package names.
- [ ] **Step 2: Run focused tests**; expected FAIL on remaining backend/frontend/metadata strings.
- [ ] **Step 3: Rebrand backend defaults and filesystem paths** without changing user/node data semantics or certificates.
- [ ] **Step 4: Rebrand frontend storage/test identifiers** and preserve backward user preference only by one-time read migration if required; no legacy token may remain in tracked code.
- [ ] **Step 5: Rebrand package/manifest metadata** and remove legacy comments/compatibility aliases that expose the old product name.
- [ ] **Step 6: Run full Python suite, compile, frontend lint/build/audit and browser responsive matrix**; expected PASS except docs still caught by source scanner.
- [ ] **Step 7: Commit** `refactor: remove legacy product identity from application source`.

### Task 4: Documentation, governance and zero-match release gate

**Files:**
- Modify: `README.md`, `README.fa.md`, `NOTICE.md`, `CHANGELOG.md`, `ROADMAP.md`, `docs/**`, `AGENTS.md`, `.github/workflows/ci.yml`
- Create: `docs/RELEASE-NOTES-v1.0.4.md`, `docs/RELEASE-NOTES-v1.0.4.fa.md`
- Test: `tests/test_pvnetwork_ownership.py`

**Interfaces:**
- Produces: zero forbidden tokens in the complete tracked tree and complete v1.0.4 docs/release notes.
- Consumes: all canonical names implemented by Tasks 1-3.

- [ ] **Step 1: Run ownership scanner** and record exact remaining documentation/governance matches; expected FAIL.
- [ ] **Step 2: Rewrite current docs/governance** to describe PVNetwork-owned upgrade/migration terminology without naming the forbidden legacy product.
- [ ] **Step 3: Update README change summaries, changelog, roadmap and v1.0.4 release notes** including backup/rollback/cutover instructions.
- [ ] **Step 4: Run tracked-tree scanner**; expected `0` forbidden matches.
- [ ] **Step 5: Run full release gate**: Python suite/compile, shell/JSON syntax, frontend lint/build/audit, browser matrix, secret scan and ownership scan; expected PASS.
- [ ] **Step 6: Commit** `docs: complete PVNetwork ownership rebrand`.

### Task 5: v1.0.4 release and Production blue/green namespace cutover

**Files:**
- Modify after evidence: `AGENTS.md`
- Production-only state: `/opt/pvnetwork-panel`, `pvnetwork-panel.service`, nginx upstream/config, rollback directory.

**Interfaces:**
- Produces: canonical PVNetwork runtime live in Production and v1.0.4 release evidence.
- Consumes: verified Task 4 release commit/artifact.

- [ ] **Step 1: Push branch/PR and require green GitHub CI** on the exact commit; build sanitized artifact + SHA256 from tracked tree.
- [ ] **Step 2: Production read-only preflight**: current PID/service, local/public API/UI, nginx upstream, DB backend/readability, Mirza 2xx continuity, disk/memory.
- [ ] **Step 3: Create and verify rollback set**: live app/runtime, systemd units/drop-ins, nginx config, `.env`, native PostgreSQL custom dump validated by `pg_restore -l`.
- [ ] **Step 4: Stage v1.0.4 under `/opt/pvnetwork-panel`** preserving only approved Production secrets/state; build frontend using the real Production URL path.
- [ ] **Step 5: Start `pvnetwork-panel.service` on a temporary local port** while the old runtime remains serving; verify local API/UI, DB reads, key routes, 0 traceback/5xx.
- [ ] **Step 6: Switch nginx upstream atomically** after `nginx -t`; reload nginx, verify public API/UI and Mirza traffic, then stop/disable the old service only after success.
- [ ] **Step 7: If any gate fails, reverse nginx first and restore the recorded runtime/service state**; leave PVN-025 `[~]`.
- [ ] **Step 8: Merge/tag/publish `v1.0.4`, verify release assets by re-download/checksum, write Production evidence to `AGENTS.md`, mark `PVN-025 [x]`, and sync the final AGENTS file to Production without unnecessary restart.

### Task 6: PostgreSQL-first runtime contract

**Files:**
- Modify: `backend/db/engine.py`, `backend/alembic/env.py`, `backend/alembic.ini`, `.env.example`, `backend/config.py`
- Create/modify tests: `tests/test_database_contract.py`
- Modify governance: `AGENTS.md`

**Interfaces:**
- Produces: explicit Production DB-mode validation and a single runtime URL source for application + Alembic.
- Consumes: canonical PVNetwork namespace from PVN-025.

- [ ] **Step 1: Register `PVN-026 [~]` target `v1.0.5` and write RED tests**: Production mode without `DATABASE_URL` raises a clear configuration error; explicit test/dev SQLite remains supported; Alembic resolves the application URL.
- [ ] **Step 2: Run** `python3 -m unittest tests.test_database_contract -v`; expected FAIL because SQLite fallback exists.
- [ ] **Step 3: Implement explicit environment-aware URL resolution**: Production requires PostgreSQL, development/test may explicitly request SQLite; remove silent Production fallback and legacy DB filename.
- [ ] **Step 4: Make PostgreSQL pool controls configurable** with conservative defaults while keeping `pool_pre_ping=True` and correct SQLite options for explicit test/dev use.
- [ ] **Step 5: Make Alembic consume the same runtime URL resolver** and remove its SQLite default.
- [ ] **Step 6: Run focused and full Python suites/compile**; expected PASS.
- [ ] **Step 7: Commit** `feat: make PostgreSQL the Production database contract`.

### Task 7: PostgreSQL provisioning, backup and migration tooling

**Files:**
- Modify: `installer.py`, `install-local.sh`, `scripts/manage.sh`, `docs/INSTALLATION.md`, `docs/UPDATES.md`
- Create: `scripts/postgres-cutover.py` or equivalent focused migration helper
- Test: `tests/test_postgres_operations.py`

**Interfaces:**
- Produces: fresh-install PostgreSQL provisioning/validation, native backup verification and deterministic parity checks for database cutover.
- Consumes: DB contract from Task 6.

- [ ] **Step 1: Write RED tests** for generated PostgreSQL URL, password handling, native dump verification command construction, protected identifier quoting, critical-table parity comparison and refusal to drop the source DB.
- [ ] **Step 2: Run focused tests**; expected FAIL because canonical provisioning/cutover helper does not yet exist.
- [ ] **Step 3: Implement fresh-install PostgreSQL provisioning/validation** without printing secrets and with idempotent validation paths.
- [ ] **Step 4: Implement migration helper** that inventories schema/row counts, validates a custom-format dump, restores into an explicitly named target and compares deterministic counts/revision before allowing cutover.
- [ ] **Step 5: Update lifecycle backup/doctor output** to verify PostgreSQL-native backup rather than treating SQLite files as Production state.
- [ ] **Step 6: Run tests plus disposable PostgreSQL integration test** using a temporary database/role and clean it up only after verification.
- [ ] **Step 7: Commit** `feat: add verified PostgreSQL provisioning and cutover tooling`.

### Task 8: v1.0.5 release and Production PostgreSQL identity cutover

**Files:**
- Modify after evidence: `AGENTS.md`, `CHANGELOG.md`, README summaries, `docs/RELEASE-NOTES-v1.0.5.md`, `docs/RELEASE-NOTES-v1.0.5.fa.md`
- Production secrets/state only: canonical database/role and `DATABASE_URL`.

**Interfaces:**
- Produces: Production running on PostgreSQL database/role `pvnetwork_panel`, v1.0.5 released and PVN-026 complete.
- Consumes: Tasks 6-7 and live PVN-025 runtime.

- [ ] **Step 1: Run complete release gate** including ownership zero-match, DB contract tests and disposable PostgreSQL integration test; require green PR CI.
- [ ] **Step 2: Production preflight and fresh native dump**; validate dump and record current schema revision, critical row counts and rollback URL separately from the app tree.
- [ ] **Step 3: Create strong-secret `pvnetwork_panel` role/database**, restore current Production DB, compare schema revision/critical row counts/constraints and start a temporary canary against it.
- [ ] **Step 4: Verify canary reads and safe write/rollback probe**; ensure Mirza/current Production remains on old DB during canary.
- [ ] **Step 5: Cut over `DATABASE_URL` atomically with the smallest possible mutation window**, restart only `pvnetwork-panel.service`, and verify local/public health, Mirza writes, user/admin reads, renewal and node assignment paths.
- [ ] **Step 6: On failure, restore prior `DATABASE_URL` and restart only the panel**; old DB remains untouched.
- [ ] **Step 7: Merge/tag/publish v1.0.5, verify assets/checksum, record parity/health/rollback evidence in `AGENTS.md`, mark `PVN-026 [x]`; retain old DB/role for rollback rather than dropping them.

### Task 9: Resume and exhaust the active AGENTS backlog

**Files:**
- Authority: `AGENTS.md`
- Existing supporting plan/spec files under `docs/superpowers/` as applicable.

**Interfaces:**
- Produces: no unresolved `[ ]` or `[~]` entries in the agreed active scope.
- Consumes: completed PVN-025/PVN-026 and the current task registry.

- [ ] **Step 1: Re-read `AGENTS.md` after v1.0.5** and enumerate every unresolved active task; never repeat `[x]` work.
- [ ] **Step 2: Execute unresolved tasks in stable-ID/release order**, using TDD, the one-Production-visible-task-per-patch rule, CI, backup/rollback and live Production verification for each visible change.
- [ ] **Step 3: After every patch**, update the ledger with exact release/commit/CI/Production evidence and continue automatically to the next unresolved task.
- [ ] **Step 4: Final project gate**: zero unresolved active tasks, zero forbidden legacy-name matches, canonical runtime/service/database live, full CI green, latest Production local/public health green, 0 new traceback/5xx, Mirza continuity confirmed.
