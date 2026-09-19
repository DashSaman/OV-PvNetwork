# PVNetwork Complete Ownership Rebrand + PostgreSQL-First Design

Date: 2026-09-19
Status: Design approved in chat; awaiting written-spec review
Target project: PVNetwork Panel

## 1. Goal

PVNetwork must be a fully owned product identity. The current `main` source tree, release artifacts, runtime paths, service names, configuration locations, backup names, frontend storage keys, metadata, installer behavior and Production runtime must not expose or depend on the legacy `ov-panel`, `ov_panel`, `ovpanel`, `OV-Panel`, or equivalent legacy product identity.

The database architecture must also be PostgreSQL-first. Production already runs PostgreSQL, so the live change is not a SQLite data migration. The work is to remove SQLite as an implicit Production default, make PostgreSQL the required Production database, and replace remaining legacy database identity with PVNetwork-owned names using a verified cutover.

## 2. Current verified state

- Current `main` contains 144 case-insensitive legacy `ov-panel`/`ovpanel` occurrences.
- The legacy runtime is currently located at `/opt/ov-panel` and uses `ov-panel.service`.
- Production database backend is already PostgreSQL through psycopg.
- Production database currently has a legacy database/user identity and must be renamed/migrated to PVNetwork-owned identity.
- Source currently silently falls back to a SQLite file when `DATABASE_URL` is absent.
- Alembic configuration still carries a SQLite URL default.
- PostgreSQL driver support already exists in project dependencies.

## 3. Canonical PVNetwork identity

The following names become canonical for all new source and runtime state:

- Product: `PVNetwork Panel`
- Install root: `/opt/pvnetwork-panel`
- systemd service: `pvnetwork-panel.service`
- system config root: `/etc/pvnetwork`
- application data root: `/var/lib/pvnetwork-panel` where host-global state is required; repo-local `data/` remains valid where intentionally bundled
- backup prefix: `pvnetwork-backup-*`
- system/logger identifier: `pvnetwork-panel`
- frontend language storage key: `pvnetwork_language`
- PostgreSQL database: `pvnetwork_panel`
- PostgreSQL role: `pvnetwork_panel`
- release/package identifiers: `pvnetwork-panel`
- lifecycle CLI: `pvnetwork` (legacy `ovpv` naming is removed from current source)

No current tracked source file may contain the forbidden legacy product tokens after the ownership rebrand gate passes. Historical Git tags remain immutable and are not rewritten.

## 4. Scope decomposition

This work is intentionally split into sequential Production-visible patches because the repository contract allows one Production-visible task per patch.

### PVN-025 / v1.0.4 — Complete ownership namespace rebrand

PVN-025 removes the legacy product identity from current source and runtime naming without changing application data semantics.

It includes:

- installer and lifecycle paths;
- systemd unit/service naming;
- runtime root and configuration paths;
- frontend storage keys and visible/internal labels;
- backup filenames and archive metadata;
- logger names;
- package/manifest metadata;
- scripts, CI, tests and documentation;
- current-source references to legacy migration branding;
- source-wide forbidden-name CI gate;
- Production blue/green runtime cutover from the old service/root to the canonical PVNetwork service/root.

PVN-025 does not change the active PostgreSQL database contents or schema solely for branding.

### PVN-026 / v1.0.5 — PostgreSQL-first + PVNetwork database identity

PVN-026 makes PostgreSQL the Production contract and replaces the remaining live legacy database identity.

It includes:

- Production startup refuses to silently use SQLite when `DATABASE_URL` is absent;
- installer provisions or validates PostgreSQL and writes a PostgreSQL URL;
- Alembic runtime URL comes from the application environment, not a SQLite default;
- connection pooling is explicitly PostgreSQL-oriented for Production;
- SQLite may remain only as an explicit test/development backend where a test opts into it;
- a new PostgreSQL role/database named `pvnetwork_panel` is created;
- the live database is copied/restored into the new PVNetwork database with row/schema verification;
- application configuration is switched atomically to the new URL;
- old database/role are retained temporarily as rollback state, then removed only after a defined soak/approval point.

## 5. Forbidden legacy-name gate

A dedicated CI/governance test scans tracked files case-insensitively for at least:

- `ov-panel`
- `ov_panel`
- `ovpanel`
- `OV-Panel`
- `OVPanel`
- legacy lifecycle prefix `ovpv`

The gate must report exact files and fail CI on any match in current `main`.

Exceptions are not allowed in current source, docs, tests, generated release metadata or release artifacts. Historical Git objects/tags are outside this rule because released history is immutable.

One-time Production migration commands may refer to the legacy live path/service as operator input during the cutover, but those commands are not committed into the clean source tree.

## 6. Production PVN-025 cutover design

Production is live and must remain serviceable. The rename therefore uses a parallel runtime cutover rather than an in-place directory rename followed by a long restart.

Required sequence:

1. Read-only preflight: service/PID, local/public API, UI, Mirza traffic, PostgreSQL readability, Nginx config, disk/memory.
2. Verified backup: application/runtime tree, systemd/drop-ins, Nginx config, `.env`, and native PostgreSQL dump.
3. Record a single rollback directory and explicit reverse-cutover commands.
4. Stage the verified `v1.0.4` tree at `/opt/pvnetwork-panel` while preserving only approved runtime secrets/state.
5. Build assets with the real Production URL path.
6. Install `pvnetwork-panel.service` on a temporary local port while the old service continues serving traffic.
7. Verify the new service locally: OpenAPI, UI, database reads, changed endpoints, integration heartbeats and logs.
8. Atomically switch Nginx upstream to the new local service and `nginx -t` before reload.
9. Verify public API/UI and critical integration traffic.
10. Stop/disable the old service only after the new public path is healthy.
11. Keep the old runtime tree and unit backup untouched until rollback window closes.
12. Record Production evidence in `AGENTS.md` before PVN-025 becomes `[x]`.

Any failed post-cutover gate switches Nginx back to the old upstream first, then restores application state if required. No database mutation is part of PVN-025.

## 7. Production PVN-026 database cutover design

The current Production database is PostgreSQL already. The re-identification uses a new database/role instead of renaming the active database in place.

Required sequence:

1. Verify current schema revision, row counts for critical tables and active DB connections.
2. Take a fresh PostgreSQL custom-format dump and validate it with `pg_restore -l`.
3. Create `pvnetwork_panel` role with least-required privileges and a strong generated password stored only in Production secrets.
4. Create `pvnetwork_panel` database owned by that role.
5. Restore/copy the current database into the new database.
6. Run Alembic status and deterministic row/count/constraint checks against both databases.
7. Start a canary PVNetwork service against the new database on a temporary local port.
8. Run read paths and safe isolated write/rollback probes where possible.
9. Quiesce only the panel mutation window if needed, take a final delta/fresh dump, and ensure no data is lost between validation and cutover.
10. Update Production `DATABASE_URL` atomically and switch/restart only `pvnetwork-panel.service`.
11. Verify local/public health, Mirza writes/heartbeats, user/admin reads, renewal paths, node assignment and logs.
12. Keep the old database/role read-only or inaccessible to the app as rollback state until the agreed soak period expires.

Rollback changes only `DATABASE_URL` back to the verified prior PostgreSQL database and restarts the panel service. The old database is never dropped during the same change window.

## 8. Database behavior after PVN-026

Production behavior:

- PostgreSQL is mandatory.
- Missing `DATABASE_URL` is a startup/configuration error, not a signal to create SQLite silently.
- Pool pre-ping remains enabled.
- Pool size/overflow/timeouts become configurable by environment with conservative defaults.
- Alembic always follows the same runtime URL source as the application.
- Backup tooling performs native PostgreSQL backup verification.

Development/test behavior:

- SQLite may be explicitly selected by tests or local development fixtures.
- SQLite-specific engine options live behind an explicit backend branch.
- No Production installer or Production default points to SQLite.

## 9. Remaining backlog execution after ownership/database work

After PVN-025 and PVN-026 are `[x]`, execution resumes the remaining open IDs from `AGENTS.md` without repeating completed work. Each Production-visible task receives the next patch release under the existing sequential-release rule.

Current open work includes PVN-022, PVN-023, PVN-117, PVN-119, PVN-120, PVN-123, PVN-125, PVN-126, PVN-132, PVN-133 and PVN-135..139.

The session/project is considered fully complete only when:

- the active `AGENTS.md` ledger has no unresolved `[ ]` or `[~]` tasks in the agreed active scope;
- current `main` passes the forbidden legacy-name scan with zero matches;
- Production uses canonical PVNetwork runtime/service names;
- Production uses the canonical PVNetwork PostgreSQL database/role;
- all applicable CI, release asset and Production health gates are green.

## 10. Testing and release gates

Each patch must pass all existing project gates plus the following relevant checks:

- full Python unit/governance suite;
- backend compile;
- frontend lint/build/audit;
- browser responsive matrix;
- secret/private-material guard;
- forbidden legacy-name scan;
- fresh-install test on a disposable Ubuntu host/container/VM where feasible;
- lifecycle update/backup/rollback script tests;
- systemd unit validation;
- PostgreSQL migration/canary tests for PVN-026;
- local and public Production health after deployment;
- zero new traceback/5xx regression;
- Mirza integration continuity.

## 11. Non-goals and safety boundaries

- Do not rewrite immutable historical tags/releases.
- Do not rotate user/node certificates or credentials as part of branding.
- Do not alter firewall, tunnel, routing or unrelated services.
- Do not combine unrelated backlog features into PVN-025/PVN-026.
- Do not drop the old PostgreSQL database in the same window as the database cutover.
- Do not claim completion from GitHub-only evidence; live Production verification remains mandatory for Production-visible work.

## 12. Acceptance criteria

PVN-025 is complete only when the current source/release artifact legacy-name scan is zero, canonical runtime naming is live on Production, old panel service is no longer serving traffic, public/local health is green, rollback remains available, and `AGENTS.md` records the evidence.

PVN-026 is complete only when PostgreSQL is the required Production default, the canonical `pvnetwork_panel` database/role is live, verified data parity and schema checks pass, the old database remains available for rollback during the defined window, Production health/integrations are green, and `AGENTS.md` records the evidence.

The broader project continuation stops only when the active `AGENTS.md` scope itself records all remaining tasks as complete or explicitly deferred/rejected with documented owner-approved reasoning.
