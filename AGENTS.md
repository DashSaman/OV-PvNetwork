# AGENTS.md — PVNetwork Panel Execution Contract

> ## CRITICAL: PRODUCTION IS LIVE AND UNDER LOAD
>
> **Assume every PVNetwork service, VPN node, database, tunnel, route, firewall rule, reseller flow, user session and integration is actively used unless explicitly proven otherwise.**
>
> Agents must NEVER make broad convenience-driven changes to Production. Do not flush firewall rules, replace default routes, restart unrelated services, rewrite node configuration wholesale, drop/recreate databases, rotate working credentials/certificates without a task-specific reason, or delete/replace existing nodes merely to simplify development.
>
> Every Production mutation follows: **backup/check → isolated/narrow change → smallest necessary restart → health verification → rollback readiness**.

## Mandatory workflow for every agent

1. Read this file before changing the project.
2. Work by a stable `PVN-xxx` task ID. IDs are never renumbered or reused.
3. Prefer branch/worktree/disposable test environments; do not develop directly on the live tree.
4. Documentation/governance work must not restart Production.
5. User-visible work must be checked on desktop, tablet and mobile, Persian RTL and English LTR, mouse/touch/keyboard, dark/light where supported.
6. A task becomes `[x]` only after focused tests, relevant regression, build/compile, responsive/accessibility checks, public-data sanitization and applicable Production health verification pass.
7. Public GitHub content must never contain Production IPs/domains, credentials, API/JWT secrets, SSH material, private keys/certificates, databases, `.ovpn`, customer/user data or unsanitized screenshots.
8. Released tags/assets are immutable. New behavior ships in a new version.
9. Every Production-visible release updates `VERSION`, `CHANGELOG.md`, release notes, bilingual docs/screenshots and GitHub Release.
10. After each completed task, report the exact `PVN-xxx` number to the user.
11. If verification is incomplete, keep the task open and record the blocker. Never claim success from assumption.
12. Applicable competitor gaps discovered in Marzban, 3X-UI, Hiddify, Remnawave, OpenVPN Access Server, Pritunl or similar panels must be recorded in the numbered registry and `docs/COMPETITOR-GAP-MATRIX.md`.
13. Every release must put a concise bilingual “what changed vs previous release” summary near the top of both README files before the long feature tour.
14. Independent read-only analysis, tests and documentation may run in parallel to reduce elapsed time. Production mutations, migrations, restarts and rollback-sensitive steps must stay serialized.
15. **GitHub-only completion is forbidden for Production-visible work.** When the human owner has authorized deployment, the exact tested release must also be applied to the authorized live Production host before the task can become `[x]`.
16. Before every Production-visible deployment, perform read-only preflight/health checks and create a verified rollback point: application/runtime backup plus a database-native backup when a database is involved. Record the rollback path before mutation.
17. Deploy only the files/build required by the tested commit. Preserve runtime `.env`, database state, certificates, node credentials, routing, firewall and unrelated host state. Never replace the live tree wholesale for convenience.
18. Backend changes may restart only `pvnetwork-panel.service` when required. Frontend-only changes should use an atomic asset/index switch and should not restart the backend unless technically necessary. Never restart VPN nodes, tunnels or unrelated services for a panel UI/backend release.
19. After deployment, verify local and public health, the changed endpoint/workflow, database readability, service restart count/state, post-deploy 5xx/traceback errors and critical integrations. If a required check fails, rollback immediately to the recorded pre-deploy state before further experimentation.
20. Production evidence must be written back into the active task ledger: deployed version/commit, backup verification, health result, rollback readiness and any restart/outage observed. A task remains `[~]` until this evidence exists.
21. **PVNetwork brand purity is permanent:** the tracked tree must contain zero references to the former upstream panel identifier in dashed, underscored, spaced or concatenated forms. Runtime paths, service/unit names, package names, UI/storage keys, backup formats/commands and new documentation must use PVNetwork-owned naming. CI must block regressions.

## Production deployment contract — owner-authorized live server

For this project, the live panel checkout is expected at `/opt/pvnetwork-panel` on the authorized Production server/session provided by the human owner. Treat it as runtime state, not as a development checkout. Development and release preparation stay in an isolated Git worktree; only the verified artifact/required files move to `/opt/pvnetwork-panel`.

Required order for every approved Production-visible release:

`read-only preflight → verified app + DB backup → rollback path recorded → narrow deploy → smallest required restart/atomic frontend switch → local health → public health → changed-workflow regression → log/integration checks → ledger evidence`

If any post-deploy gate fails, restore the pre-deploy application state and database state when applicable, restart only the panel if necessary, verify health, and keep the task open. Do not continue stacking fixes on an unhealthy Production state.

## Definition of Done

A task is DONE only when all applicable gates pass: acceptance criteria; focused tests; regression tests; frontend production build/backend compile; responsive matrix; accessibility/touch/keyboard checks; RTL/LTR; light/dark; loading/empty/error states; **owner-authorized Production deployment for every Production-visible task**; verified backup and rollback readiness; local/public post-deploy health and changed-workflow verification; sanitized public repository; changelog/docs; final health check.

## Responsive acceptance matrix

Core UI must remain usable at **360, 375, 390, 430, 768, 1024, 1366, 1440 and 1920 px**, plus **100%, 125% and 150% browser zoom**. Required actions may not become unreachable because of fixed headers, overflow, dialog height, safe areas or dropdown positioning. Touch targets should be at least 44×44 px where practical.

## Stable task ranges

- `PVN-001..099` — released baseline, critical fixes, compatibility
- `PVN-100..199` — UI/UX, responsive design, accessibility, frontend quality
- `PVN-200..299` — users, subscriptions, devices, reseller lifecycle
- `PVN-300..399` — nodes, fleet, routing, capacity, network operations
- `PVN-400..499` — monitoring, analytics, logs, reports, notifications
- `PVN-500..599` — security, RBAC, enterprise identity, audit
- `PVN-600..699` — API, Mirza, bots, webhooks, billing, automation
- `PVN-700..799` — protocols, Xray/WireGuard/Sing-box, subscription formats
- `PVN-800..899` — install, update, backup, rollback, CI/CD, HA, DR
- `PVN-900..999` — migrations, ecosystem compatibility, approved experiments

## Sequential patch-release policy

`v1.0.0` is the immutable baseline. From now on, **each completed Production-visible `PVN-xxx` task gets exactly one new patch release** in strict order: `v1.0.1` → `v1.0.2` → `v1.0.3` → ... . Do not combine multiple new Production-visible tasks into one future release, do not skip a patch number, and do not jump to a minor/major version unless the human owner explicitly changes this rule. Documentation/governance-only corrections may ride with the active task only when they do not change Production behavior.

Before implementation, record the task and target release here **and commit/push that checkpoint before risky or long-running work whenever possible**. If a chat/session is interrupted, reconnect to the persistent maintenance session, read this file, resume the first `[~]` task from its latest checkpoint/evidence, then continue with the first `[ ]` queued task; never repeat `[x]` work. Mark `[x]` only after tests, sanitization, Production-safe deployment (when applicable), health verification, GitHub merge/tag/release and release-asset verification all pass.

### Active release ledger

- `v1.0.0` — RELEASED — sanitized public baseline.
- `v1.0.1` — RELEASED — responsive/mobile hardening batch + Telegram Node DOWN/UP transition alerts + bilingual screenshots.
- `v1.0.2` — RELEASED — `PVN-111` Responsive Subscription page; CI/Production/asset verification passed.
- `v1.0.3` — RELEASED — `PVN-205` User profile/details + inline quick-edit row.
  - Requested UX shipped: expand a user row for fast edit of traffic limit, expiry, max devices, active state, node assignment, Reset Usage, Apply and Cancel.
  - Username remains intentionally read-only in this patch: safe multi-node rename is tracked separately as `PVN-022`.
  - TDD evidence: 8/8 inline-edit contract tests PASS; 3/3 safe assignment behavior tests PASS; full suite 37/37 PASS.
  - Assignment removal deactivates instead of deleting profiles; stale disabled profiles are re-used when possible; unavailable new nodes are rejected before mutation.
  - Browser evidence: focused Quick Edit smoke PASS in EN/FA at 360/390/768/1440; full responsive matrix PASS for 2 languages × 9 widths × 9 routes; Subscription responsive smoke remains PASS.
  - Sanitized FA/EN desktop/mobile Quick Edit screenshots and bilingual release/UI documentation published.
  - Main release commit `15073b80fe741b418ea7062351bbe1078e4b11ed`; GitHub CI run `35412943040` PASS including browser matrix, secret guard and production build.
  - Production evidence: verified application + native PostgreSQL backup; narrow backend/frontend deploy; local/public health 200; 0 post-deploy HTTP 5xx; Mirza integration traffic continued successfully.
  - GitHub Release `v1.0.3` published with verified artifact SHA256 `82fd4b95f2941ca8aebe323355393ce617f199b470f41930e40244a16ccb12b4`.

- `v1.0.4` — RELEASED — `PVN-025` PVNetwork brand-purity + runtime naming migration.
  - TDD RED recorded: permanent tracked-tree brand guard found legacy source/runtime identifiers before implementation.
  - Source GREEN: zero forbidden tracked-tree identifiers; metadata consistency guard; SQLite upgrade reuse; node tunnel fallback; PVNetwork-owned runtime-path tests.
  - Final local gate: 50/50 unit/governance tests PASS; Python compile, shell/JSON syntax, uv lock, ESLint, production npm audit=0 and Vite production build PASS.
  - Canonical runtime contract: `/opt/pvnetwork-panel`, `pvnetwork-panel.service`, CLI `pvnetwork`, PVNetwork-owned background jobs/timers and PVNetwork-owned backup/restore/smoke/monitor/notifier/healthcheck/config identifiers.
  - Production evidence: verified application + native PostgreSQL backup; parallel canary passed against the live database; atomic nginx cutover completed; previous live app/service retired into the rollback set; local/public health 200; 0 post-cutover HTTP 5xx; 0 Traceback/CRITICAL/FATAL; Mirza integration 2xx continued; canonical service restart count remained 0 after final cutover.
  - Main release commit `56a90462b40500096344fdf105c2c426ba0ac4cb`; GitHub CI run `35417072048` PASS including browser matrix, private-material guard and lifecycle checks.
  - GitHub Release `v1.0.4` published with verified artifact SHA256 `523ba892f33584eaec787a9e4001abe699ba3b2f6c2569a271a900b1e9fa9956`; downloaded asset checksum and tag target re-verified.

- `v1.0.5` — RELEASED — `PVN-026` user-creation node selector.
  - UX contract: Add User exposes all currently available nodes, selected by default; unavailable/draining/maintenance nodes are visible but not selectable.
  - Backend contract: explicit `node_ids` are validated before any user/quota mutation; only desired nodes are persisted and provisioned. Requests that omit `node_ids` keep backward-compatible all-available behavior.
  - Reconciliation contract: explicit assignments remain authoritative; periodic reconciliation and automatic new-node deployment may repair/provision legacy fallback users but must never widen an explicitly selected node set.
  - TDD evidence: test-only commit `9d6c9183d39a7e2bc0d191e4f1e23024272350c9` reproduced the missing contract with 5 failures + 2 errors; implementation commit `dbd4d887fba16e44371f64df407892535a3e00d3` turned the focused contract green. A second RED caught automatic new-node assignment widening; fix commit `3caf9f4c7140e0460f7534781af1304b4ae758b9` preserves explicit assignments and provisions only legacy users without assignment rows.
  - Verification: full Python unit/governance 59/59 PASS; focused Production-source assignment tests 12/12 PASS; compile/shell/JSON/uv-lock, ESLint, Vite production build and runtime npm audit PASS; largest JS 733926 bytes within budget. Browser node-selector smoke PASS in EN/FA at 360/390/768/1440; full 2-language × 9-width × 9-route matrix, Quick Edit and Subscription regressions PASS.
  - Exact-head GitHub CI run `35426637297` PASS, including browser matrix, private-material guard and lifecycle checks.
  - Production rollback point: `/root/pvnetwork-deploy-backups/v1.0.5-pvn026-20260919-063026`; application archive and native PostgreSQL dump both passed integrity verification before mutation.
  - Production deployment: exact commit `3caf9f4c7140e0460f7534781af1304b4ae758b9` passed PostgreSQL/API/UI/Push/OpenAPI canary gates on port 19002, then Nginx was switched atomically while only `pvnetwork-panel.service` was restarted on the canonical 19001 runtime.
  - Post-deploy evidence: local/public API and UI 200, JS/CSS assets 200, Push 200, CreateUser OpenAPI exposes `node_ids`, DB remained 68 users / 4 nodes / 264 assignments, changed tracked files were hash-identical to the tested commit, `REAL_ERRORS=0`, `HTTP_5XX=0`, Mirza continued with 2xx traffic, and the canary was retired after cutback to 19001.
  - Documentation checkpoint: sanitized EN/FA desktop/mobile node-selector screenshots and bilingual README/UI-guide/release-note updates prepared; no live customer/infrastructure data is used.
  - Release completion: PR #24 merged as main commit `e8ac5c531bf84fe3552c302ebc9ed8bbbb3d2cbd`; main CI run `35427077332` PASS including browser matrix and private-material guard; annotated tag `v1.0.5` resolves to the same merge commit.
  - GitHub Release `v1.0.5` published with `pvnetwork-panel-v1.0.5.tar.gz` and checksum asset. Post-publish download verification PASS: artifact SHA256 `85f9634911af9998a35d01c37565c08bf865d24c7f3bf196238973b95f2af301`, VERSION `1.0.5`, zero forbidden private-file extensions and no real `.env`.

- `v1.0.6` — RELEASED — `PVN-027` consistent online-user truth across Dashboard and Users.
  - Production discrepancy: User Management counted fresh central `active_sessions`, while Dashboard summed direct Node online counts. Read-only Production diagnosis showed central unique users=6 while a shared central+direct snapshot resolved 8 current PVNetwork users; two additional direct USA profiles were unmapped/orphan clients and are intentionally excluded from the global user count. One Node direct usage poll was unavailable.
  - Safety contract: shared presence is display/observability only. It never creates/updates `active_sessions`, does not loosen device limits, and does not change acquire/heartbeat/release enforcement. Raw per-node online/session metrics remain available on Node cards.
  - TDD RED commit `f81f9005aced1234c79b20bd7660eac59b54a00e` reproduced the missing shared-truth module/contract. Implementation checkpoint `22420052ad7467a5b312ea3754dafac3433bac00` added the shared display presence service, direct-node fallback/cache, Users wiring and Dashboard shared summary.
  - Merge semantics: fresh central session counts remain authoritative detail; direct node presence fills missing users and is deduplicated by current PVNetwork user UUID. Exact node-name suffix parsing preserves hyphenated usernames/node names; unknown/orphan clients do not inflate the global total. Transient node failures preserve central truth and may use a bounded 30-second stale direct snapshot.
  - Local verification: 67/67 Python unit/governance tests PASS; focused online/assignment/Quick Edit regression 28/28 PASS; compile/shell/JSON/uv-lock, ESLint, production build and runtime npm audit PASS; largest JS 734101 bytes within the 768000 budget.
  - Browser verification: dedicated online-truth smoke PASS in EN/FA at 390/1440 with raw Node counts intentionally summing to 5 while Dashboard and Users both must show shared unique total 3; full responsive matrix PASS for 2 languages × 9 widths × 9 routes; Quick Edit PASS; Add User Node Selector PASS; Subscription responsive smoke PASS.
  - Sanitized bilingual release notes and mock-only EN/FA desktop/mobile screenshots prepared under `docs/images/v1.0.6`; ROADMAP/README/CHANGELOG and release metadata are aligned on v1.0.6.
  - Exact-head PR #26 CI run `35428670099` PASS on commit `2f9caa4c2f721c4bb5477dfc6fb6bc14b7ca5698`, including the dedicated online-truth browser smoke, full responsive matrix, private-material guard and lifecycle checks.
  - Production rollback point: `/root/pvnetwork-deploy-backups/v1.0.6-pvn027-20260919-071519`; app archive and native PostgreSQL dump passed tar/`pg_restore -l` integrity verification before mutation.
  - Production deployment: exact commit `2f9caa4c2f721c4bb5477dfc6fb6bc14b7ca5698` passed API/UI/PostgreSQL/shared-presence canary gates on 19002. Nginx was atomically switched to the canary while only `pvnetwork-panel.service` was restarted on canonical 19001, then traffic was returned to 19001 and the canary retired.
  - Post-deploy evidence: Users and Dashboard both reported the same current unique online-user total (9 at verification time) while central hooks accounted for 7 and direct fallback supplied 2; `active_sessions` row count was unchanged by presence reads. DB remained 68 users / 4 nodes / 264 assignments; key runtime source parity 9/9 and built `frontend/dist` parity were exact; public UI/assets 200; unauthenticated protected API 401; 11/11 sampled Mirza requests were 2xx; `HTTP_5XX=0`; `REAL_ERRORS=0`; canonical service `NRestarts=0` after cutback.
  - Runtime housekeeping discovered during the authorized security review: stale Nginx `/sub-clients/` alias still referenced the removed predecessor app path. It was backed up, migrated to `/opt/pvnetwork-panel/frontend/sub_clients/`, validated with `nginx -t`, reloaded without panel restart, and the referenced asset returned HTTP 200.
  - Release completion: PR #26 merged as main commit `cc1cc9df3e6b5a23d6c63f64496bdcdbd7a0ae6c`; main CI run `35429229023` PASS including browser matrix, private-material guard and lifecycle checks; annotated tag `v1.0.6` resolves to the same merge commit.
  - GitHub Release `v1.0.6` published with source artifact + checksum. Post-publish download verification PASS: SHA256 `c4e98371c0b1ebc3279c5a8f6016b8492bb35e39453caee4cfcebc5e0b04a80e`, VERSION `1.0.6`, zero forbidden private-file extensions, and tag target re-verified.

- `v1.0.7` — RELEASED — `PVN-031` online-presence snapshot synchronization hotfix.
  - Production follow-up to `PVN-027`: Dashboard and User Management already share the same presence algorithm, but independent polling can still land on adjacent live samples.
  - Contract: one process-wide short-lived presence snapshot, a lightweight role-scoped `/users/presence` endpoint, and 1-second User Management presence refresh; no writes to `active_sessions` and no device-limit/enforcement changes.
  - TDD RED reproduced both defects: repeated presence calls repolled nodes and User Management lacked a lightweight presence endpoint. GREEN adds snapshot reuse plus a lightweight presence poll while the full user list refreshes separately at a slower cadence.
  - `PVN-028` security-hardening WIP is preserved separately and deferred to v1.0.8 so this hotfix remains the only Production-visible task in v1.0.7.
  - Verification: exact behavior commit `3b2145e5df9254f0416db88200f176cb007859f1` passed GitHub CI run `35430485225`, including unit/governance, production build, runtime audit, full browser matrix and private-material guards.
  - Production rollback point: `/root/pvnetwork-deploy-backups/v1.0.7-pvn031-20260919-075424`; app archive and native PostgreSQL dump passed integrity verification before mutation.
  - Production deployment: exact tested stage passed API/UI/DB/shared-snapshot canary gates on 19002. Nginx was switched atomically to canary while only `pvnetwork-panel.service` restarted on canonical 19001, then traffic returned to 19001 and canary was retired.
  - Production consistency proof: eight consecutive authenticated checks on canonical 19001 reported identical `presence`, Users-row and Dashboard unique-user totals with matching shared `sample_time` on every iteration (9/9/9 at verification time).
  - Post-cutover: relevant runtime source/dist hashes match the tested stage, local/public health 200, `REAL_ERRORS=0`, `HTTP_5XX=0`, sampled Mirza requests remain 2xx and canonical service `NRestarts=0`.
  - Release completion: PR #27 merged the behavior; PR #28 merged sanitized bilingual release evidence. Final main commit `f731a8e8c6fc0e69034e256df4bb2e875ec3a460`; final main CI run `35431060445` PASS including full browser matrix and private-material guard.
  - GitHub Release `v1.0.7` published at `https://github.com/DashSaman/OV-PvNetwork/releases/tag/v1.0.7`; tag resolves exactly to final main commit. Downloaded source asset SHA256 verified as `b7834159dfb0a1189f5ae331fd8985d61236576cbff08f68b90ca147e1e15ef5`, VERSION `1.0.7`, with no forbidden private-file extensions.

- `v1.0.8` — RELEASED — `PVN-028` Production security hardening from the authorized 2026-09-19 review.
  - Scope: dependency remediation + CI `pip-audit`/`bandit`; main-admin one-way password hash migration; SSH host-key pinning/verification; Production OpenAPI/Redoc reduction; security headers; login-specific throttle; AnyConnect secret-file permissions; inventory-first reversible firewall policy.
  - Safety boundary: no firewall apply, SSH lockout risk, VPN/tunnel/Xray mutation or credential cutover occurs until rollback and alternative access are proven. Existing security WIP was preserved before the v1.0.7 hotfix and resumed in isolated `release/v1.0.8`.
  - Local implementation gate: 84/84 Python unit/governance tests PASS; admin-password migration and SSH pinning have dedicated behavior tests; Python dependency audit reports zero known vulnerabilities; Bandit Medium/High gate PASS; shell/JSON/compile/uv-lock, ESLint/build and runtime npm audit PASS; largest JS 735270 bytes under the 768000 budget.
  - Browser gate: online-truth, full EN/FA responsive matrix (2 languages × 9 widths × 9 routes), Inline Quick Edit, Add User Node Selector and Subscription smoke tests all PASS. Sanitized EN/FA SSH-pinning screenshots were generated from mock-only data.
  - Host-filter design was corrected after Production inventory: existing tunnel/NFQUEUE/source-specific INPUT rules remain ahead of the final PVNetwork allow/drop chain; WireGuard/OpenVPN/Xray/tunnel configuration itself is not modified. Applying the chain requires an explicit allowlist, verified rules snapshot and timed automatic rollback until health is confirmed.
  - Final exact-head CI: commit `f9f2f39f6b80483e09f0678dc16bb47d8c82c81e`, GitHub Actions run `35433520555`, PASS including dependency/static security audits, unit/governance, frontend build/runtime audit, full browser matrix, secret/private-material guard and lifecycle checks.
  - Production rollback point: `/root/pvnetwork-deploy-backups/v1.0.8-pvn028-20260919-084536`; application archive, native PostgreSQL dump, Nginx configuration and IPv4/IPv6 firewall snapshots were captured before mutation; tar and `pg_restore -l` verification PASS.
  - Production deployment: exact tested v1.0.8 stage was validated on canary 19002, then public Nginx traffic was switched to canary while canonical 19001 was upgraded. Only `pvnetwork-panel.service` restarted; VPN/Node/Xray/tunnel services were not restarted. Public traffic returned to 19001 after health passed and the canary was retired.
  - Production security evidence: main-admin plaintext env key removed and bcrypt hash retained with `.env` mode 0600; `/openapi.json` and `/redoc` return 404; `/healthz` and public UI return 200; HSTS/CSP/nosniff/frame/referrer/permissions headers are present; public Chromium render has zero console/page errors. DB remained 68 users / 4 nodes / 264 assignments; 372/372 tracked Production files match exact release head.
  - Firewall rollout: inventory-derived allowlists were applied behind a timed rollback gate, preserving OpenVPN/Xray/X-UI/Hedioum/listeners. A confirm-parser defect was caught during live verification, rollback was safely cancelled only after health passed, TDD reproduced RED and fixed GREEN, and the final `pvnetwork-firewall-boot` apply→health→confirm path passed end-to-end. `pvnetwork-firewall-hardening.service` is enabled/persistent; no rollback timer remains; OpenVPN retained 3 live sessions; `REAL_ERRORS=0`, `HTTP_5XX=0`, and sampled Mirza traffic remained successful.
  - Frontend lifecycle regression guard: Production blank-page root cause was a build-time base-path mismatch (`/panel/` vs live `URLPATH`). The live frontend was rebuilt atomically without a service restart, public Chromium rendered with zero errors, and installer/update builds now pass the live URLPATH explicitly plus smoke-test asset-base verification.
  - Release completion: PR #30 merged as main commit `fd9afb4cf37ee862027a794a252a30a86f85fb78`; main CI run `35434082025` PASS including security audits and full browser matrix; annotated tag `v1.0.8` resolves exactly to that merge commit. GitHub Release `v1.0.8` published with source artifact + checksum; post-publish download verification PASS, SHA256 `d98fbdda5c3efd23c9b6fe47ca157ff2185231b710a3e7e441b950d3c73d0880`, VERSION `1.0.8`, zero forbidden private-file extensions.

- `v1.0.9` — IN PROGRESS — `PVN-029` opt-in Router/OpenVPN compatibility on an isolated listener/profile; normal certificate-only OpenVPN remains the default and is not modified.

## Current release baseline

- PVN-001 [x] Stable public `v1.0.0` release.
- PVN-002 [x] Expired-user renewal without delete/recreate.
- PVN-003 [x] Unlimited Reset Usage starts a new 30-day period.
- PVN-004 [x] Finite renewal preserve/reset/add-traffic modes.
- PVN-005 [x] Mirza renewal endpoint.
- PVN-006 [x] Renewal regression tests.
- PVN-007 [x] Sanitized public source release.
- PVN-008 [x] Illustrated Persian documentation baseline.
- PVN-009 [x] Illustrated English documentation baseline.
- PVN-010 [x] Release artifact + SHA256.
- PVN-011 [x] Telegram node DOWN/UP transition alerts with UI toggle and anti-spam state tracking. Released in v1.0.1.
- PVN-012 [x] Persist the non-negotiable live-Production safety contract in `AGENTS.md`.
- PVN-013 [x] Persist strict sequential patch releases from `v1.0.0` onward.
- PVN-014 [x] Persist interruption-safe Agent checkpoint/resume rules; no repeating `[x]` work.
- PVN-015 [x] Enforce one Production-visible `PVN-xxx` task per future patch release.
- PVN-016 [x] Require relevant sanitized illustrated Persian + English docs/screenshots for every visible release.
- PVN-017 [x] Require public-data/secret/forbidden-file scans before every public release.
- PVN-018 [x] Require release artifact + SHA256 upload and post-publish verification.
- PVN-019 [x] Align active Roadmap/release policy with the sequential `1.0.x` release model.
- PVN-020 [x] Every release README starts with a clear “what changed vs previous release” block in English and Persian.
- PVN-021 [x] Parallelize independent research/tests/docs when safe; never run concurrent Production mutations or restarts.
- PVN-022 [ ] Safe multi-node username rename with profile migration, rollback and no silent certificate breakage.
- PVN-023 [ ] Remove duplicate Push test route / duplicate OpenAPI Operation ID warning.
- PVN-024 [x] Enforce owner-authorized live Production deployment after verification; forbid GitHub-only completion for Production-visible work.
- PVN-025 [x] Remove every former upstream panel identifier from tracked source and migrate runtime naming to PVNetwork-owned paths/services. Release: v1.0.4.
- PVN-026 [x] User creation node selector with all available nodes selected by default; create only on selected nodes. Release: v1.0.5.
- PVN-027 [x] Unify Dashboard and Users online-user truth with a node-direct fallback when a node is not reporting central session hooks; count unique users consistently without changing device-limit enforcement. Release: v1.0.6.
- PVN-028 [x] Production security hardening from the authorized 2026-09-19 review: dependency remediation, SSH host-key pinning, main-admin credential hardening, Production API/docs/header hardening, login-specific throttling, and an inventory-preserving host-firewall policy with zero VPN/tunnel interruption. Release: v1.0.8.
- PVN-029 [~] Router/OpenVPN compatibility for RouterOS and other username/password-oriented clients using an isolated compatibility listener/profile; prefer certificate+password dual auth, keep password-only opt-in and isolated, and do not disturb existing OpenVPN certificates/listener. Target: v1.0.9.
- PVN-030 [ ] Migrate remaining legacy internal protocol/token aliases to PVNetwork-owned names with dual-read/backward-compatible rollout so existing Nodes/integrations are never cut off during the rename. Target: v1.0.10.
- PVN-031 [x] Synchronize Dashboard and User Management on one short-lived presence snapshot and lightweight live-presence polling so adjacent views do not race between samples. Release: v1.0.7.
- PVN-032 [ ] Allow the main administrator to change the panel URL path and main-admin username/password from the authenticated UI; password changes must store only a strong hash, path changes must rebuild/switch frontend atomically with rollback and must never strand the active admin session. Target: v1.0.11.

## UI/UX task ledger

- PVN-100 [x] Mobile navigation redesign. Release: v1.0.1.
- PVN-101 [x] Responsive Users page. Release: v1.0.1.
- PVN-102 [x] Responsive Nodes page. Release: v1.0.1.
- PVN-103 [x] Responsive Admins page. Release: v1.0.1.
- PVN-104 [x] Responsive Operations page. Release: v1.0.1.
- PVN-105 [x] Responsive Security page. Release: v1.0.1.
- PVN-106 [x] Responsive Fleet page. Release: v1.0.1.
- PVN-107 [x] Responsive Monitoring page. Release: v1.0.1.
- PVN-108 [x] Responsive Bandwidth page. Release: v1.0.1.
- PVN-109 [x] Responsive Dashboard. Release: v1.0.1.
- PVN-110 [x] Responsive Login page. Release: v1.0.1.
- PVN-111 [x] Responsive Subscription page. Release: v1.0.2.
- PVN-112 [x] Mobile-friendly action menus. Release: v1.0.1.
- PVN-113 [x] 44×44 touch target audit. Release: v1.0.1.
- PVN-114 [x] No page-level horizontal overflow. Release: v1.0.1.
- PVN-115 [x] Persian RTL full audit. Release: v1.0.1.
- PVN-116 [x] English LTR full audit. Release: v1.0.1.
- PVN-117 [ ] Keyboard-only navigation audit.
- PVN-118 [x] Visible focus states. Release: v1.0.1.
- PVN-119 [ ] Accessible icon-only controls.
- PVN-120 [ ] WCAG contrast audit.
- PVN-121 [x] Reduced-motion support. Release: v1.0.1.
- PVN-122 [x] Modal viewport containment and internal scrolling. Release: v1.0.1.
- PVN-123 [ ] Mobile table/card strategy for management screens.
- PVN-124 [x] Responsive pagination/search/sort controls. Release: v1.0.1.
- PVN-125 [ ] Loading, empty, error and retry states.
- PVN-126 [ ] Duplicate-submit prevention and mutation feedback.
- PVN-127 [x] Responsive Renew modal. Release: v1.0.1.
- PVN-128 [x] Responsive AnyConnect modal. Release: v1.0.1.
- PVN-129 [x] Responsive Add/Edit User flows. Release: v1.0.1.
- PVN-130 [x] Responsive Add/Edit Node flows. Release: v1.0.1.
- PVN-131 [x] Responsive Add/Edit Admin flows. Release: v1.0.1.
- PVN-132 [ ] Responsive Backup/Restore panel.
- PVN-133 [ ] Responsive Domain History/Download dialogs.
- PVN-134 [x] Playwright responsive smoke baseline. Release: v1.0.1.
- PVN-135 [ ] Accessibility smoke baseline.
- PVN-136 [ ] Desktop/mobile visual-regression baseline.
- PVN-137 [ ] Frontend bundle-size budget.
- PVN-138 [ ] Long-translation/clipped-text stress test.
- PVN-139 [ ] Persian/English typography rendering audit.

## Active user-lifecycle task ledger

- PVN-205 [x] User profile/details + inline quick-edit row. Release: v1.0.3.

## High-priority capability backlog index

The detailed numbered registry is maintained in `docs/FEATURE-BACKLOG.md` and must be read together with this file. It explicitly includes: periodic traffic reset; scheduled renewal; multi-stage notifications; device inventory/revoke/HWID; self-service portal; QR and multi-format subscriptions; user/reseller analytics; Prometheus/Grafana/logs; granular RBAC; OIDC/Passkey/LDAP/RADIUS/SAML; node capacity/admission/failover; route/split-tunnel/GeoIP/GeoSite policies; background jobs/retry queues; generic signed webhooks; Telegram management bot; migration/import/export; WireGuard/Xray/VLESS/VMess/Trojan/Shadowsocks/REALITY/Hysteria2/TUIC/Sing-box; Base64/Xray/Sing-box/Clash/Mihomo subscriptions; WARP/outbound pools/chaining/load balancing/failover; installer/update/backup/rollback/HA/DR hardening; and client compatibility tests.

No applicable gap may exist only in prose: it must receive a stable `PVN-xxx` ID in `docs/FEATURE-BACKLOG.md` and a mapping in `docs/COMPETITOR-GAP-MATRIX.md`.

## Required companion documents

- `ROADMAP.md` — public release-level summary.
- `docs/FEATURE-BACKLOG.md` — complete numbered product backlog.
- `docs/COMPETITOR-GAP-MATRIX.md` — competitor capability → PVNetwork state → `PVN-xxx`.
- `docs/UX-AUDIT.md` — page/modal/workflow UX status.
- `docs/QA-RELEASE-GATE.md` — blocking release checks.
- `design-system/pvnetwork/MASTER.md` — design/interaction source of truth.
- `docs/superpowers/specs/2026-09-19-agent-roadmap-ux-design.md` — approved governance design.
- `docs/superpowers/plans/2026-09-19-governance-and-ux-hardening.md` — implementation plan.

## Completion evidence format

```text
PVN-127 [x] Responsive Renew modal
Release: v1.0.N
Commit: <sha>
Tests: <exact commands/results>
Docs: <paths>
Production: HEALTH=PASS or N/A
```

## Release rule

Follow the **Sequential patch-release policy** above. Released tags/assets are immutable; every new production-visible batch advances exactly one patch version.

## Complete mirrored task registry

This section intentionally mirrors the complete permanent task registry so an agent reading only `AGENTS.md` cannot miss a capability gap. `docs/FEATURE-BACKLOG.md` remains the human-readable grouped view. IDs must stay identical in both files.

## PVN-100..199 — UI/UX, responsive, accessibility

- PVN-100 Mobile navigation redesign
- PVN-101 Responsive Users page
- PVN-102 Responsive Nodes page
- PVN-103 Responsive Admins/Resellers page
- PVN-104 Responsive Operations Center
- PVN-105 Responsive Security page
- PVN-106 Responsive Fleet page
- PVN-107 Responsive Monitoring page
- PVN-108 Responsive Bandwidth page
- PVN-109 Responsive Dashboard
- PVN-110 Responsive Login
- PVN-111 Responsive Subscription page
- PVN-112 Mobile-safe row/action menus
- PVN-113 44×44 touch-target audit
- PVN-114 No page-level horizontal overflow
- PVN-115 Persian RTL full audit
- PVN-116 English LTR full audit
- PVN-117 Keyboard-only navigation
- PVN-118 Visible focus states
- PVN-119 Accessible names for icon-only controls
- PVN-120 WCAG contrast audit
- PVN-121 Reduced-motion support
- PVN-122 Viewport-bounded/scrollable modals
- PVN-123 Mobile table/card/details strategy
- PVN-124 Responsive search/sort/pagination
- PVN-125 Loading/empty/error/retry states
- PVN-126 Duplicate-submit prevention
- PVN-127 Responsive Renew modal
- PVN-128 Responsive AnyConnect modal
- PVN-129 Responsive Add/Edit User flows
- PVN-130 Responsive Add/Edit Node flows
- PVN-131 Responsive Add/Edit Admin flows
- PVN-132 Responsive Backup/Restore panel
- PVN-133 Responsive Domain History/Download dialogs
- PVN-134 Automated responsive smoke baseline
- PVN-135 Accessibility smoke baseline
- PVN-136 Desktop/mobile visual regression baseline
- PVN-137 Frontend bundle-size budget
- PVN-138 Long-translation/clipped-text stress test
- PVN-139 Persian/English typography rendering audit
- PVN-140 Mobile safe-area handling
- PVN-141 Dropdown viewport-edge positioning
- PVN-142 Dropdown Escape/focus return
- PVN-143 Dialog focus trap where applicable
- PVN-144 Dialog focus return
- PVN-145 Accessible async status/live regions
- PVN-146 Color-independent status cues
- PVN-147 Responsive charts
- PVN-148 Accessible chart legends/tooltips
- PVN-149 Layout-shift prevention
- PVN-150 Lazy loading for heavy docs imagery
- PVN-151 Image alt-text audit
- PVN-152 No hover-only critical action
- PVN-153 Destructive-action touch spacing
- PVN-154 Accessible copy-to-clipboard feedback
- PVN-155 Route-level error boundary
- PVN-156 Unsaved-form navigation warning where needed
- PVN-157 360px full-flow audit
- PVN-158 375px full-flow audit
- PVN-159 390px full-flow audit
- PVN-160 430px full-flow audit
- PVN-161 768px tablet audit
- PVN-162 1024px small-desktop audit
- PVN-163 1366px laptop audit
- PVN-164 1440px desktop audit
- PVN-165 1920px full-HD audit
- PVN-166 125% browser zoom audit
- PVN-167 150% browser zoom audit
- PVN-168 Mobile navigation overflow/More destination
- PVN-169 Header action density on small screens
- PVN-170 Sticky action behavior on short screens
- PVN-171 Form inline validation consistency
- PVN-172 Form helper/error text consistency
- PVN-173 Required-field semantics
- PVN-174 Mobile numeric-input ergonomics
- PVN-175 RTL/LTR directional-icon audit
- PVN-176 Consistent SVG/icon system
- PVN-177 Shared spacing tokens
- PVN-178 Shared typography tokens
- PVN-179 Shared semantic color tokens
- PVN-180 Dark-mode contrast audit
- PVN-181 Light-mode contrast audit
- PVN-182 Mobile Backup table strategy
- PVN-183 Subscription client cards mobile layout
- PVN-184 Subscription server cards mobile layout
- PVN-185 Subscription credentials copy UX
- PVN-186 Client-download card accessibility
- PVN-187 Long username/domain/token wrapping
- PVN-188 Touch-friendly pagination
- PVN-189 Touch-friendly sort controls
- PVN-190 Touch-friendly filter controls
- PVN-191 Mobile destructive confirmation UX
- PVN-192 Dialog short-height landscape audit
- PVN-193 Tablet landscape audit
- PVN-194 High-DPI icon rendering audit
- PVN-195 Screen-reader label audit
- PVN-196 Skip/reliable navigation landmark audit
- PVN-197 Semantic heading hierarchy audit
- PVN-198 Reduced-motion regression test
- PVN-199 UI/UX release sign-off

## PVN-200..299 — user, subscription, device and reseller lifecycle

- PVN-200 Periodic traffic-reset schedules
- PVN-201 Scheduled renewal rules
- PVN-202 Multi-stage expiry notifications
- PVN-203 Configurable traffic-threshold notifications
- PVN-204 Improved self-service user portal
- PVN-205 User profile/details page + inline quick-edit row
- PVN-206 Per-user device inventory
- PVN-207 Revoke device/session
- PVN-208 HWID/device-limit mode
- PVN-209 Session history
- PVN-210 Manual session termination
- PVN-211 QR connection outputs
- PVN-212 Subscription usage summary
- PVN-213 Subscription renewal CTA
- PVN-214 User CSV export
- PVN-215 User Excel export
- PVN-216 Bulk user import
- PVN-217 Bulk expiry edit
- PVN-218 Bulk traffic-quota edit
- PVN-219 Bulk node assignment
- PVN-220 User notes/tags
- PVN-221 User groups
- PVN-222 Group-level policies
- PVN-223 Reseller traffic-ledger UI
- PVN-224 Reseller unlimited-slot ledger UI
- PVN-225 Reseller quota alerts
- PVN-226 Reseller user transfer
- PVN-227 Reseller-scoped node visibility
- PVN-228 Reseller-scoped reports
- PVN-229 User lifecycle audit timeline
- PVN-230 User archive/restore
- PVN-231 Soft-delete option
- PVN-232 Grace period after expiry
- PVN-233 Traffic carry-over option
- PVN-234 Custom billing-cycle anchor
- PVN-235 Plan templates
- PVN-236 Plan catalog
- PVN-237 Plan clone
- PVN-238 Per-plan default node set
- PVN-239 Per-plan notification policy
- PVN-240 User timezone preference
- PVN-241 Localized subscription page
- PVN-242 Per-reseller subscription branding
- PVN-243 Subscription custom-domain support
- PVN-244 User/self-service API token
- PVN-245 Download history
- PVN-246 Connection history summary
- PVN-247 Last-seen details
- PVN-248 Multi-protocol identity model
- PVN-249 User migration wizard
- PVN-250 Scheduled suspension/reactivation
- PVN-251 Bulk renew
- PVN-252 Renewal preview/dry-run
- PVN-253 Renewal history
- PVN-254 Quota top-up history
- PVN-255 Per-user notification opt-in policy
- PVN-256 Subscription link rotation
- PVN-257 Subscription link revoke
- PVN-258 User ownership-transfer audit
- PVN-259 Reseller child-admin model
- PVN-260 Reseller permission templates
- PVN-261 Reseller API tokens
- PVN-262 Reseller webhook scope
- PVN-263 User labels as automation selectors
- PVN-264 Group bulk actions
- PVN-265 Group node assignment
- PVN-266 Group bandwidth policy
- PVN-267 Group route policy
- PVN-268 Group notification policy
- PVN-269 User import validation report
- PVN-270 Import duplicate-resolution policy
- PVN-271 Export sanitized support view
- PVN-272 Account clone with new identity
- PVN-273 Plan-change workflow
- PVN-274 Prorated plan-change metadata
- PVN-275 Future-start account date
- PVN-276 Fixed end-date plan
- PVN-277 Manual expiry override with audit
- PVN-278 Per-user node preference
- PVN-279 Per-user failover preference
- PVN-280 Per-user connection notes
- PVN-281 User search by owner/node/tag/status
- PVN-282 Saved user filters
- PVN-283 User list column preferences
- PVN-284 User-list mobile detail drawer
- PVN-285 User batch-progress UI
- PVN-286 User operation partial-failure report
- PVN-287 Subscription client-detection rules
- PVN-288 Subscription client guide by platform
- PVN-289 One-click/deep-link connection where supported
- PVN-290 Subscription download telemetry (privacy-safe)
- PVN-291 Renewal push notification sync
- PVN-292 Expiry push notification sync
- PVN-293 Traffic-threshold push notification sync
- PVN-294 Per-user notification history
- PVN-295 User webhook event history
- PVN-296 Reseller dashboard KPIs
- PVN-297 Reseller daily/monthly usage summary
- PVN-298 Reseller export bundle
- PVN-299 User lifecycle release sign-off

## PVN-300..399 — nodes, fleet, routing and network operations

- PVN-300 Node capacity thresholds
- PVN-301 Admission control
- PVN-302 Node cost metadata
- PVN-303 Node traffic-cost metadata
- PVN-304 Maintenance scheduling
- PVN-305 Drain scheduling
- PVN-306 Automatic failover on unhealthy node
- PVN-307 Weighted assignment policies
- PVN-308 Geographic assignment policy
- PVN-309 Latency-aware assignment
- PVN-310 Node labels/tags
- PVN-311 Node groups
- PVN-312 Host abstraction
- PVN-313 Reusable config profiles
- PVN-314 Node capability negotiation
- PVN-315 Node agent/version inventory
- PVN-316 Upgrade rings/canary groups
- PVN-317 Node version rollback
- PVN-318 Config-drift detection
- PVN-319 Config reconciliation
- PVN-320 Node API-key/certificate rotation
- PVN-321 Ephemeral SSH credential handling
- PVN-322 Node install dry-run
- PVN-323 Node install preflight report
- PVN-324 Node uninstall workflow
- PVN-325 Node decommission workflow
- PVN-326 Node pre-upgrade backup
- PVN-327 Node diagnostic bundle
- PVN-328 Node journal/log snapshot
- PVN-329 Node connectivity test matrix
- PVN-330 OpenVPN port reachability test
- PVN-331 Node API reachability test
- PVN-332 Node DNS test
- PVN-333 Public-IP change detection
- PVN-334 Disk-pressure alert
- PVN-335 Bandwidth-saturation alert
- PVN-336 Connection-limit alert
- PVN-337 Reboot-required indicator
- PVN-338 Kernel/network-tuning report
- PVN-339 Split-tunnel route-policy editor
- PVN-340 Per-user/group destination policy
- PVN-341 GeoIP policy management
- PVN-342 GeoSite policy management
- PVN-343 Custom route import/export
- PVN-344 Routing-rule validation
- PVN-345 Routing-policy preview/dry run
- PVN-346 Routing-policy canary apply
- PVN-347 Routing-policy rollback
- PVN-348 Outbound-pool abstraction
- PVN-349 Load-balancer rules
- PVN-350 Failover rules
- PVN-351 Proxy chaining
- PVN-352 WARP outbound integration
- PVN-353 Custom SOCKS/HTTP outbound
- PVN-354 Traffic-steering analytics
- PVN-355 Node user/session capacity forecast
- PVN-356 Node health-history timeline
- PVN-357 Node incident timeline
- PVN-358 Node maintenance notes
- PVN-359 Node quarantine mode
- PVN-360 Automatic quarantine trigger
- PVN-361 Safe node resume verification
- PVN-362 Fleet operation approval gate
- PVN-363 Fleet job cancel
- PVN-364 Fleet job progress streaming
- PVN-365 Fleet partial-failure rollback
- PVN-366 Fleet upgrade compatibility check
- PVN-367 Fleet DB migration compatibility check
- PVN-368 Node clock-drift check
- PVN-369 MTU diagnostic
- PVN-370 MSS diagnostic
- PVN-371 Routing-table diagnostic
- PVN-372 Firewall-rule diagnostic
- PVN-373 No-flush firewall reconciler
- PVN-374 Route-change safety guard
- PVN-375 Tunnel/interface preservation test
- PVN-376 Existing-service preservation test
- PVN-377 Node PostgreSQL/x-ui coexistence check
- PVN-378 Node CPU saturation policy
- PVN-379 Node RAM saturation policy
- PVN-380 Node disk saturation policy
- PVN-381 Node health-score explanation UI
- PVN-382 Node assignment reason UI
- PVN-383 Rebalance explanation UI
- PVN-384 Rebalance preview
- PVN-385 Rebalance exclusion rules
- PVN-386 Manual pin/no-rebalance user flag
- PVN-387 Maintenance-aware subscriptions
- PVN-388 Drain-aware smart recommendation
- PVN-389 Node geographic metadata
- PVN-390 Node provider metadata
- PVN-391 Node cost center metadata
- PVN-392 Node bandwidth cap metadata
- PVN-393 Node owner/team metadata
- PVN-394 Node capacity dashboard
- PVN-395 Route-policy audit history
- PVN-396 Outbound-policy audit history
- PVN-397 Fleet compatibility matrix
- PVN-398 Network-operation regression suite
- PVN-399 Node/fleet release sign-off

## PVN-400..499 — monitoring, analytics, logs, reports and notifications

- PVN-400 Prometheus metrics endpoint
- PVN-401 Official Grafana dashboard
- PVN-402 Long-term node traffic history
- PVN-403 Long-term per-user traffic history
- PVN-404 Configurable metric retention
- PVN-405 Top users analytics
- PVN-406 Top nodes analytics
- PVN-407 Peak bandwidth analytics
- PVN-408 Concurrent-session analytics
- PVN-409 Node-health trend charts
- PVN-410 Alert history
- PVN-411 Central log viewer
- PVN-412 Structured audit-log viewer
- PVN-413 Searchable operations log
- PVN-414 Sanitized support/diagnostic bundle
- PVN-415 Scheduled email reports
- PVN-416 Scheduled Telegram reports
- PVN-417 CSV reports
- PVN-418 Excel reports
- PVN-419 PDF reports
- PVN-420 Per-reseller reports
- PVN-421 Per-node reports
- PVN-422 Per-user reports
- PVN-423 Traffic anomaly detection
- PVN-424 Sudden session-spike detection
- PVN-425 Disk-usage forecasting
- PVN-426 Bandwidth forecasting
- PVN-427 Notification-provider abstraction
- PVN-428 Email notifications
- PVN-429 Telegram management notifications
- PVN-430 Generic webhook notifications
- PVN-431 Slack/Discord-compatible webhooks
- PVN-432 Notification templates
- PVN-433 Per-event notification routing
- PVN-434 Notification retry queue
- PVN-435 Notification delivery history
- PVN-436 Maintenance notification suppression
- PVN-437 Metrics health self-test
- PVN-438 Synthetic node probe
- PVN-439 Status endpoint
- PVN-440 Optional public status page
- PVN-441 SLO/SLA dashboard
- PVN-442 API latency histogram
- PVN-443 Database latency metrics
- PVN-444 Queue-depth metrics
- PVN-445 Job-duration metrics
- PVN-446 Error-rate dashboard
- PVN-447 HTTP status-code analytics
- PVN-448 Slow endpoint report
- PVN-449 Node API latency percentiles
- PVN-450 Subscription endpoint latency
- PVN-451 Backup duration/history
- PVN-452 Restore duration/history
- PVN-453 Upgrade duration/history
- PVN-454 Per-node session timeline
- PVN-455 Per-user concurrency timeline
- PVN-456 Data export retention policy
- PVN-457 Log retention policy
- PVN-458 Audit retention policy
- PVN-459 Metrics storage sizing guide
- PVN-460 Alert deduplication
- PVN-461 Alert grouping
- PVN-462 Alert acknowledgement
- PVN-463 Alert escalation
- PVN-464 Maintenance windows
- PVN-465 Notification quiet hours
- PVN-466 Reseller notification scoping
- PVN-467 Per-node alert thresholds
- PVN-468 Per-group alert thresholds
- PVN-469 User threshold override
- PVN-470 Monitoring backup/export
- PVN-471 Grafana provisioning bundle
- PVN-472 Prometheus scrape-auth option
- PVN-473 External SIEM webhook
- PVN-474 Health endpoint dependency detail
- PVN-475 Readiness/liveness separation
- PVN-476 DB pool metrics
- PVN-477 Background-job metrics
- PVN-478 Node sync metrics
- PVN-479 Mirza integration metrics
- PVN-480 AnyConnect auth metrics
- PVN-481 Domain-activity metrics privacy controls
- PVN-482 Dashboard date-range controls
- PVN-483 Dashboard saved views
- PVN-484 Report scheduler UI
- PVN-485 Report download center
- PVN-486 Report permission model
- PVN-487 Report redaction mode
- PVN-488 Report watermarking optional
- PVN-489 Monitoring mobile layout
- PVN-490 Monitoring accessibility audit
- PVN-491 Chart colorblind-safe palettes
- PVN-492 Data freshness indicator
- PVN-493 Stale-data warning
- PVN-494 Partial-node-data warning
- PVN-495 Monitoring regression suite
- PVN-496 Notification integration tests
- PVN-497 Metrics cardinality guard
- PVN-498 Observability performance budget
- PVN-499 Observability release sign-off

## PVN-500..599 — security, RBAC, enterprise identity and audit

- PVN-500 Granular RBAC permissions
- PVN-501 Custom roles
- PVN-502 Role templates
- PVN-503 OAuth2/OIDC admin authentication
- PVN-504 Passkey/WebAuthn
- PVN-505 LDAP authentication
- PVN-506 RADIUS authentication/accounting
- PVN-507 SAML SSO
- PVN-508 Admin session management
- PVN-509 Admin session revoke
- PVN-510 Admin device history
- PVN-511 Admin login history
- PVN-512 Brute-force protection dashboard
- PVN-513 Security-event audit
- PVN-514 IP allowlist UI validation
- PVN-515 Token scope editor
- PVN-516 Token expiry/last-used UI
- PVN-517 Token rotation workflow
- PVN-518 Secret rotation playbook
- PVN-519 Node API-key rotation
- PVN-520 JWT rotation strategy
- PVN-521 Backup encryption
- PVN-522 Backup signing
- PVN-523 Restore integrity verification
- PVN-524 Security-header audit
- PVN-525 Content Security Policy baseline
- PVN-526 CSRF posture audit
- PVN-527 CORS validation
- PVN-528 Cookie/session hardening
- PVN-529 Dependency vulnerability scan
- PVN-530 Container/image scan where applicable
- PVN-531 SAST baseline
- PVN-532 Secret scanning CI
- PVN-533 Git-history secret scan
- PVN-534 Public screenshot sanitization check
- PVN-535 PII redaction in support bundle
- PVN-536 Audit-log tamper-resistance strategy
- PVN-537 Two-person approval for destructive fleet actions
- PVN-538 Break-glass admin procedure
- PVN-539 Account lockout recovery
- PVN-540 2FA recovery codes
- PVN-541 Trusted-device policy
- PVN-542 Password policy UI
- PVN-543 Password breach-check optional
- PVN-544 Database least-privilege role
- PVN-545 Read-only reporting DB role
- PVN-546 Security release checklist
- PVN-547 Admin inactivity timeout
- PVN-548 Concurrent admin-session policy
- PVN-549 Admin IP/device notification
- PVN-550 Sensitive-action reauthentication
- PVN-551 Token one-time reveal policy
- PVN-552 Secret-field copy audit
- PVN-553 Restore authorization gate
- PVN-554 Bandwidth emergency-action authorization gate
- PVN-555 Fleet upgrade authorization gate
- PVN-556 Security settings change audit
- PVN-557 RBAC permission-diff UI
- PVN-558 Role migration tooling
- PVN-559 SSO fail-open/fail-closed policy
- PVN-560 LDAP/RADIUS connection test UI
- PVN-561 SAML metadata validation
- PVN-562 OIDC discovery validation
- PVN-563 Passkey recovery policy
- PVN-564 Security audit export
- PVN-565 Audit event signing optional
- PVN-566 API abuse-rate analytics
- PVN-567 API token anomaly detection
- PVN-568 Node-auth anomaly detection
- PVN-569 Login geo/IP anomaly indicator
- PVN-570 Secure default settings audit
- PVN-571 Environment-variable validation
- PVN-572 Startup secret-strength validation
- PVN-573 TLS configuration audit
- PVN-574 Certificate-expiry dashboard
- PVN-575 Let's Encrypt status UI
- PVN-576 Automated TLS renewal health check
- PVN-577 CSP report-only rollout
- PVN-578 Security dependency pinning
- PVN-579 Supply-chain checksum policy
- PVN-580 Release artifact signature verification
- PVN-581 Admin backup download authorization
- PVN-582 Backup sensitive-data inventory
- PVN-583 DB backup access policy
- PVN-584 Sanitized bug-report exporter
- PVN-585 Security regression tests
- PVN-586 RBAC regression tests
- PVN-587 SSO integration tests
- PVN-588 TOTP recovery tests
- PVN-589 API-token tests
- PVN-590 IP allowlist lockout guard
- PVN-591 Emergency recovery access procedure
- PVN-592 Security documentation bilingual refresh
- PVN-593 Threat-model document
- PVN-594 Data-flow privacy inventory
- PVN-595 Public-repository privacy checklist
- PVN-596 Security issue template
- PVN-597 Vulnerability disclosure workflow
- PVN-598 Security release audit
- PVN-599 Security release sign-off

## PVN-600..699 — API, Mirza, bots, webhooks, billing and automation

- PVN-600 Generic outbound webhooks
- PVN-601 Webhook signing
- PVN-602 Webhook retry/dead-letter
- PVN-603 Billing provisioning templates
- PVN-604 Billing suspension webhook
- PVN-605 Billing renewal webhook
- PVN-606 Billing traffic top-up webhook
- PVN-607 Telegram management bot
- PVN-608 Telegram user lookup/renew
- PVN-609 Telegram node health actions
- PVN-610 Telegram emergency policy actions
- PVN-611 Mirza full lifecycle parity
- PVN-612 Mirza bulk operations
- PVN-613 Mirza webhook callbacks
- PVN-614 API idempotency keys
- PVN-615 API request correlation IDs
- PVN-616 API pagination consistency
- PVN-617 API filtering consistency
- PVN-618 API versioning policy
- PVN-619 OpenAPI examples
- PVN-620 SDK generation baseline
- PVN-621 CLI admin client
- PVN-622 Event-bus abstraction
- PVN-623 Background job queue
- PVN-624 Retry queue for offline nodes
- PVN-625 Scheduled-jobs subsystem
- PVN-626 Job cancel/retry UI
- PVN-627 Job progress streaming
- PVN-628 Import/export API
- PVN-629 Migration API
- PVN-630 Plugin/integration registry
- PVN-631 External monitoring integration
- PVN-632 External SIEM webhook
- PVN-633 Prometheus auth option
- PVN-634 Grafana provisioning files
- PVN-635 Webhook event replay
- PVN-636 Webhook delivery log
- PVN-637 Billing event audit
- PVN-638 API request audit search
- PVN-639 API rate-limit headers
- PVN-640 API error schema standardization
- PVN-641 Bulk API job model
- PVN-642 Async operation status endpoint
- PVN-643 Mirza auth rotation
- PVN-644 Integration health dashboard
- PVN-645 Integration per-tenant scopes
- PVN-646 Telegram command RBAC
- PVN-647 Telegram 2FA/confirmation for destructive actions
- PVN-648 Billing provider adapter interface
- PVN-649 Generic CRM webhook adapter
- PVN-650 Generic accounting export adapter
- PVN-651 Job priority classes
- PVN-652 Job concurrency limits
- PVN-653 Job timeout policy
- PVN-654 Job cancellation semantics
- PVN-655 Job result retention
- PVN-656 API deprecation headers
- PVN-657 API compatibility tests
- PVN-658 OpenAPI breaking-change detector
- PVN-659 API client examples Persian/English
- PVN-660 Integration secrets vault abstraction
- PVN-661 Webhook allowlist/denylist
- PVN-662 Outbound webhook proxy option
- PVN-663 Billing dry-run endpoint
- PVN-664 Provisioning preview endpoint
- PVN-665 Provisioning rollback endpoint
- PVN-666 Scheduled renewal automation worker
- PVN-667 Periodic reset automation worker
- PVN-668 Notification automation worker
- PVN-669 Offline-node reconciliation worker
- PVN-670 Daily integrity-check worker
- PVN-671 Audit export worker
- PVN-672 Report generation worker
- PVN-673 Retry/backoff policy library
- PVN-674 Idempotent node mutation helpers
- PVN-675 Idempotent user mutation helpers
- PVN-676 API documentation portal
- PVN-677 Public API changelog
- PVN-678 Integration test sandbox
- PVN-679 Demo webhook receiver
- PVN-680 API performance budget
- PVN-681 API latency SLO
- PVN-682 Mirza latency/error metrics
- PVN-683 Webhook latency/error metrics
- PVN-684 Bot latency/error metrics
- PVN-685 API token usage analytics
- PVN-686 Integration retry dashboard
- PVN-687 Integration disabled-state handling
- PVN-688 Integration maintenance windows
- PVN-689 Integration event schema versioning
- PVN-690 Event replay safety guard
- PVN-691 Webhook payload redaction policy
- PVN-692 Billing payload redaction policy
- PVN-693 API docs secret/example scan
- PVN-694 API fuzz/smoke baseline
- PVN-695 Integration contract tests
- PVN-696 Mirza regression suite
- PVN-697 Bot regression suite
- PVN-698 Webhook regression suite
- PVN-699 Integration release sign-off

## PVN-700..799 — protocols, Xray/WireGuard/Sing-box and subscription formats

- PVN-700 WireGuard core integration
- PVN-701 Xray core integration
- PVN-702 VLESS
- PVN-703 VMess
- PVN-704 Trojan
- PVN-705 Shadowsocks
- PVN-706 REALITY
- PVN-707 Hysteria2
- PVN-708 TUIC
- PVN-709 Sing-box integration
- PVN-710 Multi-protocol user identity
- PVN-711 Protocol capability discovery
- PVN-712 Protocol-specific quota accounting
- PVN-713 Protocol-specific session limits
- PVN-714 Raw/Base64 subscriptions
- PVN-715 Xray JSON subscription
- PVN-716 Sing-box subscription
- PVN-717 Clash/Mihomo subscription
- PVN-718 User-Agent subscription negotiation
- PVN-719 Subscription template editor
- PVN-720 Subscription response rules
- PVN-721 Protocol-aware node assignment
- PVN-722 Protocol-aware health checks
- PVN-723 Protocol-aware analytics
- PVN-724 Mixed-protocol subscription page
- PVN-725 Protocol-specific client guides
- PVN-726 One-click client deep links
- PVN-727 Fallback inbound configuration
- PVN-728 Multi-inbound management
- PVN-729 Single-port fallback
- PVN-730 TLS/REALITY key lifecycle
- PVN-731 Geo asset updater
- PVN-732 Xray routing editor
- PVN-733 Sing-box route editor
- PVN-734 Protocol migration assistant
- PVN-735 Protocol feature flags
- PVN-736 Protocol rollout canary
- PVN-737 Protocol rollback
- PVN-738 Protocol node capability matrix
- PVN-739 Protocol-specific port management
- PVN-740 Protocol-specific certificate management
- PVN-741 WireGuard peer/device model
- PVN-742 WireGuard QR output
- PVN-743 WireGuard route policy
- PVN-744 Xray inbound templates
- PVN-745 Xray outbound templates
- PVN-746 REALITY key rotation
- PVN-747 Hysteria2/TUIC certificate workflow
- PVN-748 Sing-box config-profile templates
- PVN-749 Clash/Mihomo profile templates
- PVN-750 Base64 template customization
- PVN-751 Subscription format preview
- PVN-752 Subscription format validation
- PVN-753 Client User-Agent analytics privacy-safe
- PVN-754 Protocol connection diagnostics
- PVN-755 Protocol install preflight
- PVN-756 Protocol node upgrade compatibility
- PVN-757 Protocol traffic reconciliation
- PVN-758 Cross-protocol quota sharing
- PVN-759 Cross-protocol device limit
- PVN-760 Cross-protocol expiry handling
- PVN-761 Cross-protocol renewal
- PVN-762 Cross-protocol audit events
- PVN-763 Cross-protocol notifications
- PVN-764 Protocol-specific rate limiting
- PVN-765 Protocol-specific routing policies
- PVN-766 Outbound pool per protocol
- PVN-767 Load balancing per protocol
- PVN-768 Failover per protocol
- PVN-769 Protocol maintenance/drain behavior
- PVN-770 Protocol node smart recommendation
- PVN-771 Protocol health score
- PVN-772 Protocol metrics Prometheus labels
- PVN-773 Protocol Grafana panels
- PVN-774 Protocol admin mobile UX
- PVN-775 Protocol subscription mobile UX
- PVN-776 Protocol permissions/RBAC
- PVN-777 Protocol reseller scopes
- PVN-778 Protocol billing metadata
- PVN-779 Protocol migration dry-run
- PVN-780 Protocol migration rollback
- PVN-781 Protocol compatibility test suite
- PVN-782 Karing multi-format compatibility
- PVN-783 v2rayNG compatibility
- PVN-784 V2Box compatibility
- PVN-785 Mihomo compatibility
- PVN-786 Sing-box client compatibility
- PVN-787 WireGuard client compatibility
- PVN-788 Xray core version pinning
- PVN-789 Sing-box version pinning
- PVN-790 GeoIP/GeoSite version pinning
- PVN-791 Protocol release channel
- PVN-792 Protocol security audit
- PVN-793 Protocol privacy audit
- PVN-794 Protocol docs Persian
- PVN-795 Protocol docs English
- PVN-796 Protocol illustrated guides
- PVN-797 Protocol regression suite
- PVN-798 Universal-control-plane readiness gate
- PVN-799 Protocol release sign-off

## PVN-800..899 — install, update, backup, rollback, CI/CD, HA and DR

- PVN-800 `pvnetwork status`
- PVN-801 `pvnetwork doctor`
- PVN-802 `pvnetwork backup`
- PVN-803 `pvnetwork update`
- PVN-804 `pvnetwork rollback`
- PVN-805 Migration verification before update
- PVN-806 Automatic rollback on failed health
- PVN-807 Stable/beta release channels
- PVN-808 Fresh-install CI on disposable environment
- PVN-809 Disposable node auto-deploy E2E
- PVN-810 Installer OS preflight
- PVN-811 Installer disk/RAM preflight
- PVN-812 Installer port-conflict check
- PVN-813 Existing-service safety check
- PVN-814 Installer PostgreSQL setup option
- PVN-815 Installer Nginx setup option
- PVN-816 Installer TLS/Let's Encrypt option
- PVN-817 Minimal firewall-rule option
- PVN-818 Installer idempotency
- PVN-819 Installer noninteractive mode
- PVN-820 Node-installer idempotency
- PVN-821 Node-install rollback
- PVN-822 Node-installer checksum verification
- PVN-823 Update artifact checksum verification
- PVN-824 Signed release artifacts
- PVN-825 SBOM generation
- PVN-826 Dependency-lock verification
- PVN-827 DB backup before migration
- PVN-828 DB restore rehearsal
- PVN-829 PostgreSQL HA guide
- PVN-830 Control-plane HA guide
- PVN-831 Reverse-proxy HA guide
- PVN-832 Disaster-recovery runbook
- PVN-833 Automated DR restore test
- PVN-834 Release candidate checklist
- PVN-835 Release smoke test
- PVN-836 Upgrade-from-previous test
- PVN-837 Rollback-to-previous test
- PVN-838 Changelog automation
- PVN-839 Release-notes automation
- PVN-840 Screenshot refresh workflow
- PVN-841 Docs link checker
- PVN-842 Public-data/secret scan gate
- PVN-843 Branch protection policy
- PVN-844 Required CI status checks
- PVN-845 Conventional commit policy
- PVN-846 Version-bump automation
- PVN-847 Release artifact retention
- PVN-848 Support matrix documentation
- PVN-849 Upgrade compatibility matrix
- PVN-850 tmux/persistent maintenance session runbook
- PVN-851 Remote access watchdog/service for maintenance connector
- PVN-852 Maintenance session naming/ownership policy
- PVN-853 Read-only Production health command
- PVN-854 Pre-deploy backup manifest
- PVN-855 Post-deploy health manifest
- PVN-856 Rollback verification manifest
- PVN-857 Database migration dry run
- PVN-858 Database migration checksum
- PVN-859 Schema drift detection
- PVN-860 Dependency update policy
- PVN-861 Node.js/Python supported-version policy
- PVN-862 Ubuntu/Debian support matrix tests
- PVN-863 Fresh-server installer screenshot/guide
- PVN-864 Node-installer screenshot/guide
- PVN-865 Update screenshot/guide
- PVN-866 Rollback screenshot/guide
- PVN-867 Backup/restore screenshot/guide
- PVN-868 Installer telemetry-free policy
- PVN-869 Installer secret-output minimization
- PVN-870 Installer generated-password handling
- PVN-871 Installer CORS/public URL validation
- PVN-872 Installer reverse-proxy validation
- PVN-873 Installer health retry policy
- PVN-874 Update lock to prevent concurrent upgrades
- PVN-875 Backup lock to prevent conflicting restore
- PVN-876 Restore maintenance-mode workflow
- PVN-877 Release asset reproducibility
- PVN-878 Reproducible frontend build check
- PVN-879 Python dependency reproducibility
- PVN-880 Release artifact content manifest
- PVN-881 Release artifact secret scan
- PVN-882 Release artifact forbidden-file scan
- PVN-883 Release checksum verification docs
- PVN-884 Release signature verification docs
- PVN-885 Release known-issues section
- PVN-886 Release upgrade notes
- PVN-887 Release rollback notes
- PVN-888 Node compatibility notes
- PVN-889 DB migration notes
- PVN-890 Backup compatibility notes
- PVN-891 Release smoke on fresh install
- PVN-892 Release smoke on upgrade
- PVN-893 Release smoke on rollback
- PVN-894 Production canary deploy procedure
- PVN-895 Production health observation window
- PVN-896 Release incident rollback procedure
- PVN-897 Release postmortem template
- PVN-898 Release automation regression suite
- PVN-899 Operations release sign-off

## PVN-900..999 — migration and ecosystem compatibility

- PVN-900 Import from Marzban
- PVN-901 Import from 3X-UI
- PVN-902 Import from Hiddify
- PVN-903 Import from Remnawave
- PVN-904 Import from generic OpenVPN CSV
- PVN-905 Migration dry-run report
- PVN-906 Migration rollback snapshot
- PVN-907 Legacy upstream-panel migration assistant
- PVN-908 Subscription compatibility checker
- PVN-909 Client compatibility matrix
- PVN-910 Karing compatibility test
- PVN-911 v2rayNG compatibility test
- PVN-912 V2Box compatibility test
- PVN-913 Mihomo compatibility test
- PVN-914 OpenVPN Connect compatibility test
- PVN-915 Cisco AnyConnect client compatibility test
- PVN-916 Mobile Safari subscription test
- PVN-917 Android Chrome subscription test
- PVN-918 Desktop browser subscription test
- PVN-919 Internationalization translation coverage
- PVN-920 RTL screenshot regression
- PVN-921 LTR screenshot regression
- PVN-922 Public demo mode
- PVN-923 Demo-data generator
- PVN-924 Sanitized documentation snapshot generator
- PVN-925 Import field-mapping UI
- PVN-926 Import duplicate strategy
- PVN-927 Import validation errors UI
- PVN-928 Import rollback UI
- PVN-929 Migration audit trail
- PVN-930 Client version support matrix
- PVN-931 Client deep-link support matrix
- PVN-932 Client QR support matrix
- PVN-933 Client subscription format matrix
- PVN-934 Client troubleshooting guide
- PVN-935 OS/browser compatibility matrix
- PVN-936 Mobile safe-area compatibility matrix
- PVN-937 RTL browser compatibility
- PVN-938 Accessibility browser compatibility
- PVN-939 Upgrade migration from v1.0
- PVN-940 Upgrade migration from legacy/future minor-version schemes
- PVN-941 DB schema compatibility validator
- PVN-942 API compatibility validator
- PVN-943 Subscription backward-compatibility validator
- PVN-944 Node-agent compatibility validator
- PVN-945 Node version migration assistant
- PVN-946 External panel discovery import wizard
- PVN-947 Sanitized migration report export
- PVN-948 Demo-mode read-only guard
- PVN-949 Public demo reset scheduler
- PVN-950 Ecosystem regression suite
- PVN-951 Client guide screenshots Persian
- PVN-952 Client guide screenshots English
- PVN-953 Karing guide
- PVN-954 OpenVPN Connect guide
- PVN-955 AnyConnect guide
- PVN-956 v2rayNG guide
- PVN-957 V2Box guide
- PVN-958 Mihomo guide
- PVN-959 Sing-box guide
- PVN-960 WireGuard guide
- PVN-961 Windows compatibility audit
- PVN-962 Android compatibility audit
- PVN-963 iOS compatibility audit
- PVN-964 Linux compatibility audit
- PVN-965 macOS compatibility audit
- PVN-966 Browser download behavior audit
- PVN-967 Subscription MIME/content-type audit
- PVN-968 Content-Disposition filename audit
- PVN-969 Unicode username/download filename audit
- PVN-970 QR encoding audit
- PVN-971 Clipboard compatibility audit
- PVN-972 Push notification browser support matrix
- PVN-973 PWA install support matrix
- PVN-974 Offline admin shell behavior
- PVN-975 Demo/privacy disclaimer
- PVN-976 Open-source attribution audit
- PVN-977 License compatibility audit
- PVN-978 Public issue template privacy warning
- PVN-979 Public bug-report sanitization guide
- PVN-980 Public support bundle sanitizer
- PVN-981 Migration performance benchmark
- PVN-982 Large-user-count UI benchmark
- PVN-983 Large-node-count UI benchmark
- PVN-984 Large-session-count benchmark
- PVN-985 Subscription page performance benchmark
- PVN-986 Mobile performance benchmark
- PVN-987 Low-bandwidth admin usability test
- PVN-988 High-latency admin usability test
- PVN-989 Offline-node partial-failure UX test
- PVN-990 Browser refresh/state recovery test
- PVN-991 Session-expiry UX test
- PVN-992 API outage UX test
- PVN-993 DB outage recovery UX test
- PVN-994 Node outage recovery UX test
- PVN-995 Cross-version restore compatibility test
- PVN-996 Ecosystem docs link checker
- PVN-997 Public docs screenshot sanitizer test
- PVN-998 Ecosystem release audit
- PVN-999 Ecosystem release sign-off

## Rule

Every applicable capability discovered later receives an unused stable ID in the correct range. Never recycle an ID from a completed, rejected, deferred or superseded item. Competitor-derived tasks remain research inputs until Product fit and Production safety are confirmed.
