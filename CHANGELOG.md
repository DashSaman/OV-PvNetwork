## v1.0.35 — PVN-1019 presence rate-dict hotfix

- /users/presence was returning 500 since the split-rate change: the endpoint still coerced each rate to float while the payload had become {down, up, total} dicts — the very reason live speeds stopped appearing in the panel. Rates now pass through as dicts with a type guard; verified live (all presence requests 200 after deploy).

## v1.0.34 — PVN-1018 stable speed column + chart units + daily renewal digest

- The Users table gains a dedicated Speed (↓/↑) column — always visible for online users (0 Kbps when idle instead of a chip appearing and disappearing), cyan download / amber upload, stacked on phones; the inline name chip was removed.
- Fixed an 8× unit error in the live charts: node rates are bytes/s while the recharts axes format bits/s, so the dashboard total could read ~300 Mbps while the chart plotted ~26. Both the dashboard area chart and the node sparklines now convert bytes→bits.
- Renewal Telegram alerts are now a single consolidated digest per 24 hours (all active expiry/traffic reminders in one message, timestamp persisted in monitor state) instead of separate messages.

## v1.0.33 — PVN-1017 split ↓/↑ per-user speeds + per-node sparklines

- Each online user now shows separate live download and upload speeds beside their name (↓ cyan / ↑ amber chips) instead of a combined figure: nodes report per-client rx and tx through an idempotent additive patch (combined totals untouched for quota accounting), and /users/presence returns down/up/total per uuid.
- Every dashboard node card gains a live recharts sparkline of that node's download history (rolling window, hover tooltip, per-node accent color) in the shared lazy chart chunk.
- The subscription-page renewal permission popup now appears at most once a week instead of daily.

## v1.0.32 — PVN-1016 live per-user speed + professional charts

- The Users table now shows each connected user's live traffic rate (⚡ x.x Mbps) right beside their username, updated every presence poll — computed on the panel from per-CN cumulative usage deltas across all nodes and exposed through /users/presence (rates_bps_by_uuid). Offline or idle users show no chip.
- The dashboard live traffic chart was rebuilt with recharts (gradient areas, live tooltip, formatted axis) in its own lazy chunk so the main bundle stays within budget; the previous SVG chart remains as the Suspense fallback.

## v1.0.31 — PVN-1015 Vengeance-style professional skin

- A new token-level skin gives the admin panel a professional Vengeance-inspired look: layered near-black surfaces, a single vibrant amber accent with glow, glass cards and modals (backdrop blur), hairline borders, gradient primary buttons with hover lift, dark input wells with accent focus rings, slim scrollbars and reduced-motion safety. Loaded after the core stylesheets so it only overrides visual tokens — every existing class keeps working and deleting the single skin file rolls the look back.
- Speed: nginx now gzips JavaScript/JSON/SVG/webmanifest responses (main bundle 982 KB → 297 KB, −70%) and serves hashed panel assets with a one-year immutable cache; BBR + fq were already active and persisted. Telegram monitor: the v1.0.30 hotfix stopped the live repeat loop.

## v1.0.30 — PVN-1014 renewal-alert repeat hotfix

- Fixes the live Telegram spam introduced in v1.0.28: renewal keys persisted in the monitor state were fed into the generic node-alert transition builder, which announced them as “Resolved” on every monitor tick and immediately re-added them — an endless message loop. Renewal keys are now excluded from the generic builder and keep their own silent-clear transitions; regression tests pin both the wiring and the exact spam path.

## v1.0.29 — PVN-1013 installable panel (PWA) + mobile users-table cards

- The admin panel is now installable (PWA web manifest with icons and standalone display): Add to Home Screen on Android/iOS or Install App in desktop browsers gives PVNetwork its own app window and icon.
- On phones (≤640px) the Users table transforms into stacked cards per user — no more horizontal scrolling — while keeping the full table on larger screens.

## v1.0.28 — PVN-202/203 renewal notifications (expiry + traffic)

- The Telegram monitor now sends renewal alerts for active users: expiry stages at 7, 3, 1 and 0 days remaining (nearest stage only, one message per stage) and traffic thresholds at 80/90/100 percent of the quota. Alerts fire once when the condition appears and clear silently when the user renews or the usage resets, reusing the existing transition-dedup state so nothing spams.
- Delivered through the existing monitoring toggle (same bot token/chat); no new settings, no OpenVPN/Node/Router changes.

## v1.0.27 — PVN-1001 firewall boot fix + PVN-540 2FA recovery codes

- Fixes the host firewall boot service that had failed on every boot since 2026-09-22: on Ubuntu 24.04 with socket-activated SSH, ssh.service is inactive at boot time until the first connection, so the required-service check always failed. The check now accepts ssh.socket/sshd.service as satisfying ssh.service (inventory-first rules and the built-in timed rollback are unchanged).
- Adds one-time 2FA recovery codes: enabling TOTP now generates eight codes (bcrypt-hashed at rest), shown exactly once in Security Settings with a copy-all button; if the authenticator is unavailable, any unused code substitutes for the 6-digit code on the login page and is consumed. Disabling TOTP clears the codes, and the settings page shows the remaining count. Migration g9a0b1c2d3e4 creates the table.

## v1.0.26 — PVN-1012 Router password viewable in the admin panel

- Router/MikroTik credentials now store a reversible Fernet ciphertext (keyed from the panel secret, same pattern as AnyConnect) so the password is viewable afterwards in the admin panel: the user Router/MikroTik dialog shows the current password under the username, with a hint to rotate once for credentials created before this release.
- The on-create one-time warning now states that the password also remains viewable in the admin panel (13 languages).
- Alembic migration adds the nullable password_ciphertext column; legacy rows stay one-time-only until rotated. No OpenVPN, Node or Router listener behavior changes.

## v1.0.25 — PVN-1011 Router readiness probe + actionable credential errors

- Root cause of the missing username/password report: Router/MikroTik capability was never enabled on any node (the capability table was empty), so every on-create credential request failed with a bare 409 and the results panel showed no credentials.
- The Add User Router checkbox now probes the live Router status of every selected node when ticked and shows the verdict inline: ready-node count, or a red enable instruction (Nodes → Router/MikroTik → Preflight → Enable) when none are ready — before anything is submitted.
- Credential failures in the results panel translate into actionable messages (capability not enabled, listener unhealthy, node needs upgrade) instead of raw 409 details; all strings are translated in the 13 shipped languages.

## v1.0.24 — PVN-1009 subscription runtime revived + MikroTik on-create panel fixed

- Root-caused and fixed the dead subscription-page runtime: the strict CSP shipped in v1.0.8 (script-src 'self' without unsafe-inline) silently blocked every inline script on the public /sub page — language/theme switching, the renewal countdown (stuck on "در حال محاسبه زمان باقی‌مانده..."), copy buttons and the QR overlay all never executed. The subscription page now serves a dedicated CSP allowing inline scripts on that path only; the admin panel keeps the strict policy. Migrating the template to nonces is registered as the follow-up.
- The vendored QR library is now served by the backend at /sub-assets/qr/ with a correct JavaScript MIME type; the nginx /sub-clients/ location overrides its types{} map and was handing the file out as application/octet-stream, which browsers refuse to execute under nosniff.
- Fixed the Router/MikroTik on-create panel: POST /users/ now returns {name, uuid} (the bare name made the results panel unreachable), the results panel shows each node's server address next to its credentials, gains a per-node Router-profile download button and a built-in MikroTik/RouterOS step-by-step tutorial; legacy backends fall back to a name-based uuid lookup.

## v1.0.23 — PVN-211 smart subscription page (QR + per-device guides)

- The public subscription page gains a page-level QR (open the subscription on another device) and a per-server QR button that renders that config's download URL for phone-camera scanning.
- QR codes are generated client-side by the vendored MIT `qrcode-generator` (Kazuhiko Arase), served same-origin from `/sub-clients/qr/` — no CDN and CSP-safe; attribution added to `NOTICE.md`.
- A per-device quick-connect guide (Windows, macOS, iPhone/iPad, Android, Linux, MikroTik/Router) was added to the subscription page in Persian and English, including the Router credential flow from v1.0.21.
- First item of the owner-approved five-release track recorded in `ROADMAP.md` (subscription QR → self-service portal → Telegram bot → import/export + groups → renewal notifications → WireGuard bridge).
- No API, authentication, OpenVPN, Node, Router listener or session changes.

## v1.0.22 — PVN-1008 reliable automatic node deployment

- Fixes the most common Add-Node auto-install failure: the "Panel public IP" field defaulted to the browser hostname, which is not an IP when the panel runs behind a domain/proxy — deployment aborted with a raw validation error, and a manually-typed wrong IP made the node firewall block the panel so verification failed after a full install. The field is now optional and, when empty or not a literal IP, the node derives the true panel source address from the SSH session itself (always the path the panel API will use), with the decision logged in the deployment terminal.
- Fixes an intermittent firewall-stage failure: allow rules were inserted at INPUT position 2, which errors on servers with fewer existing rules; rules are now inserted at position 1 with existence guards and the DROP rule appended at the end. IPv6 panel sources get a matching ip6tables allow branch instead of the previous blanket IPv6 drop that could lock out IPv6 panels.
- Verification failures after installation now produce an actionable message (node API unreachable — check the firewall between panel and node) instead of a bare timeout.
- Add-Node SSH field labels moved into the translation catalogs (13 languages); focused contract tests added for the auto-detect mode, firewall-rule shape, IPv6 branch, optional schema and modal behavior.

## v1.0.21 — PVN-1006 full language uniformity (values and raw strings)

- Fixes the remaining mixed-language UI: 28 catalog keys carried Persian values inside the English catalog and the other 11 non-Persian catalogs (backup/security/transfer/2FA labels showed Persian under every non-Persian language); the Backup/Restore panel, AnyConnect user modal, reseller-deletion dialogs and parts of the user/renewal forms were entirely hardcoded Persian with no translation calls at all.
- Every catalog now carries real translations for those keys, and ~100 previously hardcoded strings across 7 components now go through the translation system (563 used keys resolve in all 13 languages).
- The Backup panel direction now follows the active language (previously forced RTL) and its timestamps format in the active locale.
- Permanent CI gates extended: non-Persian catalogs must contain zero Arabic-script values, the Arabic catalog must contain zero Persian-only characters, and no component may contain raw Persian text outside translation calls.

## v1.0.20 — PVN-1005 uniform language switching

- Fixes mixed-language UI: 45 keys (reseller/unlimited-account labels, renewal modal, sort menu, action buttons, copy feedback, navigation labels and more) were missing from every language catalog and rendered their hardcoded Persian or English defaults regardless of the selected language. All keys now exist and are translated in all 13 shipped languages.
- The Router/MikroTik modal direction now follows the active language (`direction` key: RTL for Persian/Arabic, LTR otherwise) instead of being fixed RTL.
- Two remaining hardcoded English error messages (download-from-node flows) now go through the translation catalog.
- Adds a permanent catalog-parity gate: every `t()` key used anywhere in the frontend must resolve in every shipped language, blocking future regressions.
- No API, authentication, OpenVPN, Node, Router listener or session behavior changes.

## v1.0.19 — PVN-1003 white-screen regression fix, index no-cache and i18n completion

- Fixes the live white-screen introduced by the v1.0.18 frontend deployment: a locally built bundle embedded the wrong asset base path (`/panel/` instead of the deployed panel path), so the SPA shell loaded but its JS/CSS 404'd. The release build contract now documents that `URLPATH` (the variable Vite actually reads) must match the deployed panel path.
- The SPA `index.html` is now served with `Cache-Control: no-cache`, so an atomic asset/index switch can never again strand browsers on a cached old index whose hashed assets no longer exist.
- Completes 35 missing UI translation keys (Quick Edit, node selector, Router/MikroTik, username rename) in all 11 secondary languages; every shipped language file now covers the full 407-key catalog.
- Production database and login role renamed from the legacy pre-rebrand identifier to `pvnetwork_panel` with a verified backup-first migration (31 tables / 71 users / 4 nodes parity, Alembic head preserved, old database retained as rollback).
- No OpenVPN, Node, Router listener, profile or session behavior changes.

## v1.0.18 — PVN-1002 panel release-version badge

- The Dashboard header now shows the running panel release version (for example `v1.0.18`) directly next to the LIVE · REALTIME indicator.
- The version is read at runtime from the public `/healthz` endpoint, so the badge always reflects the actually deployed backend release without a rebuild assumption.
- Display-only: no API contract, authentication, OpenVPN, Node, Router listener, profile or session behavior changes.

## v1.0.17 — PVN-1000 debounced CPU threshold alerts

- CPU threshold alerts now require two consecutive at-threshold samples before firing and two consecutive recovered samples (with a 5-point recovery margin) before sending Resolved, eliminating transient CPU alert flapping.
- Threshold alert state and per-key consecutive-sample counters are persisted in the monitor state file, so a monitor restart cannot re-fire an already-active alert.
- Offline nodes no longer keep stale CPU threshold counters alive; counters for keys that are neither live nor active are dropped.
- RAM, disk, sync-availability and SSL alerts keep their existing transition semantics; no OpenVPN, Node, Router listener, profile or session behavior is changed.

## v1.0.16 — PVN-022 safe multi-node username rename

- Added durable job/lock orchestration for username rename with resumable staging, cutover, rollback and cleanup.
- Preserves user UUID/accounting/assignments plus UUID-bound AnyConnect and Router/MikroTik identities.
- Stages and verifies new per-node OpenVPN identities before cutover; old identities are disabled/disconnected then immediately revoked after commit with no grace period.
- Blocks conflicting user mutations while rename owns the durable lifecycle lock.
- Adds bilingual Rename Username UI, job recovery after refresh and dedicated worker/timer.
- Normal OpenVPN is never restarted by the rename workflow.

## v1.0.15 — PVN-376 / PVN-398 per-user OpenVPN lifecycle preservation

- Removes whole-service OpenVPN restarts from normal per-user Enable/Disable/Delete lifecycle.
- Disable/Delete disconnect only the target Common Name through the normal-listener management socket while preserving other active sessions.
- Existing Node capability upgrades now apply the user-lifecycle no-restart patch, closing the previous `--router-only` upgrade gap.
- Delete uses direct EasyRSA revoke + CRL generation/publication and removes only target-client PKI leaf artifacts after successful revocation; it no longer depends on an optional interactive installer.
- Adds idempotent Node patch and isolated behavior regression tests, including exact-CN matching and a no-`systemctl restart` contract.
- No database migration and no intended normal OpenVPN listener/configuration change.

## v1.0.14 — PVN-585 security regression

- Adds permanent regression coverage for authentication, API-token scopes, IDOR/identifier handling, CORS/CSRF posture, XSS, SQL interpolation, route protection, output redaction and sensitive-file permissions.
- Fixes the reproduced reverse-proxy IP inconsistency by sharing one trusted client-IP parser between middleware and Security Settings allowlist validation.
- Prevents API tokens from acting as interactive main administrators for Security, panel runtime settings or backup administration.
- Restricts database API-token fallback to supported `pvn_` / legacy `ovp_` prefixes and replaces substring scope classification with exact resource-prefix classification, including nested Operations/AnyConnect/Router-OpenVPN paths.
- Adds a credential-free, GET-only Production security probe plus a mocked-browser XSS regression and explicit GitHub Actions security gate.
- No SSO/RBAC/session architecture, OpenVPN listener, Node, firewall, routing or live VPN-session behavior is added by this patch.

## v1.0.13 — PVN-894 safe Production canary retirement

- Adds a fail-closed canary retirement guard that refuses retirement while the active Nginx site still points at canary port `19002` or does not point at canonical port `19001`.
- Requires an explicit active Nginx site, `nginx -t`, a successful Nginx reload, canonical local `/healthz` HTTP 200, and public `/healthz` HTTP 200 before an operator may retire the release canary.
- Emits machine-readable `CANARY_RETIRE_SAFE=YES/NO` evidence for release automation and manual rollout logs.
- This patch is a direct regression guard for the v1.0.12 rollout incident where the canary was stopped before Nginx had been cut back to canonical, briefly producing public HTTP 502.
- No OpenVPN, Router listener, Node, certificate, profile, routing, firewall or active VPN-session behavior is changed.

## v1.0.12 — PVN-032 runtime main-admin and panel-path settings

- Adds authenticated Security Settings controls for the main-admin username, password and panel URL path; every mutation re-verifies the current password and stores only the password hash.
- Main-admin JWTs are generation-bound so successful credential rotation invalidates older main-admin browser sessions while the initiating browser receives a guarded replacement-token handoff.
- Path changes build and verify a candidate panel on `127.0.0.1:19002`, switch atomically, and roll back the panel environment/frontend if canonical verification fails.
- The previous panel path returns HTTP 307 to the new path for exactly 300 seconds, preserving the suffix, then naturally returns 404.
- OpenVPN listeners, Router compatibility listeners, `ov-node.service`, VPN profiles, certificates, routing and active user tunnels are outside the mutation path and are never restarted by PVN-032.
- Release rollout hardens control-plane checks: Node health probes use the actual `GET /sync/status` JSON-body contract, and the panel smoke test reads only `PORT`/`URLPATH` instead of sourcing secret-bearing `.env` values and discovers nested FastAPI routes through the in-process schema.

## v1.0.11 — PVN-033 live online-count truth regression fix

- Treats a successful Node `/sync/usage` response with `data: null` as a fresh zero-client snapshot instead of a failed poll, preventing stale online clients from surviving the display grace window.
- Adds managed per-Node online counts to the shared presence snapshot so Dashboard Node cards and the global/User Management totals use the same current PVNetwork-user truth.
- Unknown/orphan OpenVPN Common Names remain excluded from managed-user totals and are reported separately as unmapped presence evidence; no profile, certificate or enforcement session is mutated by this patch.
- Device-limit acquire/heartbeat/release semantics, normal OpenVPN listeners and Node services remain unchanged.

## v1.0.10 — PVN-030 backward-compatible protocol alias migration

- New API tokens use the PVNetwork-owned `pvn_` prefix while existing `ovp_` tokens remain valid.
- Node integrations accept `X-PVNetwork-Node-Key` and the legacy `X-OV-Node-Key`; conflicting dual headers are rejected.
- PVNetwork-injected Node helper aliases migrate from `_ov_*` to `_pvnetwork_*` during Node upgrade without requiring existing Nodes to upgrade immediately.
- Upstream-owned `primeZdev/ov-node`, `/opt/ov-node` and `ov-node.service` identities are intentionally unchanged.
- Normal OpenVPN listeners, profiles and credentials are not modified by this patch.

## v1.0.9 — PVN-029 Router / MikroTik OpenVPN compatibility

- Adds an opt-in secondary OpenVPN listener per compatible Node; the normal certificate-only listener/profile remains unchanged.
- Adds certificate + password dual authentication for RouterOS/legacy clients, with per-user/per-node credentials and one-time plaintext password display only.
- Adds Node preflight, isolated enable/disable/rollback, profile generation, capability upgrade detection and raw secondary-listener observability.
- Merges secondary Common Names into display-only online presence without double counting and without synthesizing enforcement sessions.
- Adds bilingual Node/User Router flows and a RouterOS import command while keeping normal OpenVPN downloads credential-free.

## v1.0.8 — PVN-028 Production security hardening

- main-admin password hash migration with rollback-safe deployment
- Production health endpoint and docs/schema gating
- dedicated login throttling and security headers
- explicit SSH host-key fingerprint pinning; no first-seen auto-trust
- dependency/static security CI gates with zero known Python advisories
- reversible inventory-preserving firewall helper with timed rollback
- existing certificate-only OpenVPN listener/profile behavior unchanged

## 1.0.7 — 2026-09-19

PVN-031 online-presence synchronization hotfix.

- Added one process-wide short-lived display-presence snapshot to prevent near-simultaneous Dashboard and Users requests from repolling different node states.
- Added a lightweight role-scoped `/users/presence` endpoint.
- User Management now refreshes live presence every second without reloading the complete user list every second; full-list refresh remains slower and separate.
- No database migration and no writes to `active_sessions`; device-limit/session enforcement is unchanged.

## 1.0.6 — 2026-09-19

PVN-027 consistent online-user truth release.

### Online presence
- Added a shared display-only presence layer that merges fresh central sessions with direct node usage snapshots.
- Deduplicates current PVNetwork users across nodes and maps direct client names using the exact node-name suffix.
- Ignores unknown/orphan node clients in the global user total while preserving raw per-node metrics.
- Added short direct-node caching, bounded stale grace and fail-open central-state preservation for transient node polling failures.

### Enforcement safety
- Does not create/update `active_sessions`; device-limit and session acquire/heartbeat/release semantics are unchanged.
- No database migration and no node/tunnel/firewall/certificate changes.

### QA
- Added focused central/direct merge, dedup, hyphenated-name, unknown-client and failure-mode tests.
- Added Dashboard-vs-Users browser regression with intentionally divergent raw node totals in EN/FA mobile and desktop viewports.

## 1.0.5 — 2026-09-19

PVN-026 user-creation node-selection release.

### User creation
- Added a node selector to Add User with every available node selected by default.
- Offline, draining and maintenance nodes remain visible but cannot be selected.
- Added `node_ids` to the create-user contract; omitted `node_ids` preserves legacy all-available behavior.
- Node selection is validated before user creation or reseller-entitlement mutation, then persisted in the same transaction.
- Immediate node provisioning is limited to the stored assignment and remains fail-open for temporary node/API outages.

### Reconciliation safety
- Explicit `user_nodes` rows are authoritative and are never widened by the scheduled reconciler.
- Legacy users with no assignment rows retain all-available fallback behavior.
- Reconciliation skips nodes in drain/maintenance state while still repairing missing profiles on desired available nodes.

### Responsive / QA
- Added English/Persian browser smoke at 360, 390, 768 and 1440 px for default selections, unavailable-node disabling, POST payload and mobile touch/overflow behavior.
- Full existing responsive, Quick Edit and Subscription browser matrices remain regression gates.
- Added sanitized English/Persian desktop/mobile screenshots.

### Compatibility
- No database schema migration.
- Existing user UUIDs, certificates and assignments are not rewritten by this release.
- Firewall, routing, tunnels and unrelated services remain outside scope.

# Changelog

## 1.0.4 — 2026-09-19

PVNetwork brand-purity and runtime-ownership release.

### Product ownership
- Removed every former upstream panel identifier from the tracked source tree and added a blocking CI regression guard.
- Canonicalized package, API, frontend and release metadata on PVNetwork Panel `1.0.4`.
- Preserved MIT copyright attribution without carrying the former product brand into PVNetwork source.

### Runtime naming
- Canonical runtime path is `/opt/pvnetwork-panel`; service is `pvnetwork-panel.service`.
- Renamed PVNetwork-owned backup/restore, push, monitoring, fleet and configuration paths.
- Installer/update logic now resolves releases from `DashSaman/OV-PvNetwork`.
- Existing SQLite deployments safely reuse a single discovered `.db` file when the canonical database file is not present.
- Language preference is now stored under `pvnetwork_language` while generically importing a valid predecessor `*_language` value once.

### Safety
- No schema migration. PostgreSQL data is unchanged.
- Production migration uses verified backup/rollback, parallel canary runtime and an atomic reverse-proxy switch; VPN nodes, tunnels, routes, firewall rules and certificates are outside scope.

## 1.0.3 — 2026-09-19

Inline user quick-edit and assignment-safety patch.

### User management
- Added expandable Quick Edit from each user row for traffic quota, expiry where policy permits, device limit, active state, assigned nodes and queued Reset Usage.
- Kept username read-only; safe multi-node rename is tracked separately as `PVN-022`.
- User list responses now expose effective `node_ids`, including backward-compatible legacy all-node assignments.

### Multi-node safety
- Added guarded assignment replacement: removals deactivate instead of deleting profiles/certificates.
- Re-adding a stale disabled profile attempts safe reuse before generating anything new.
- Newly assigned offline/draining/maintenance nodes are rejected before mutation.
- Normal user edits and status changes synchronize only assigned nodes.

### Responsive / QA
- Quick Edit reflows outside the wide management table on <=992px layouts and keeps primary actions at a 44px touch floor.
- Added focused Quick Edit browser smoke in English/Persian at phone/tablet/desktop widths.
- Corrected the browser-test language key to the real `pvnetwork_language`, so RTL/LTR checks now exercise the actual application language.
- Added sanitized English/Persian desktop/mobile Quick Edit screenshots.

### Compatibility
- No database migration.
- No intended firewall, routing, tunnel, certificate rotation or unrelated-service changes.


## 1.0.2 — 2026-09-19

Subscription-page mobile usability patch.

### Subscription UX
- Raised mobile notification, Linux-copy and AnyConnect-copy controls to the 44px touch floor.
- Kept long usernames, hostnames and credentials bounded within the viewport.
- Added automated FA/EN responsive checks at 360, 375, 390, 430, 768, 1024 and 1440 px.
- Added sanitized Persian/English desktop/mobile Subscription screenshots.

### Governance
- Aligned active roadmap/install/update/QA documentation with strict sequential `1.0.x` releases.
- Added explicit interruption-safe Agent checkpoint rules and one Production-visible PVN task per future patch.

### Compatibility
- No database migration.
- No routing, firewall, tunnel, node or user-lifecycle behavior change.

## 1.0.1 — 2026-09-19

Compatibility-preserving UI/UX, responsive and project-governance hardening release.

### Monitoring
- Added explicit Telegram node state transitions: `🔴 Node DOWN` on offline transition and `🟢 Node UP` on recovery.
- Added a Monitoring Settings toggle for node online/offline alerts; unchanged node states are not resent.

### Responsive and accessibility
- Added complete Main Admin mobile navigation with an accessible More menu for Admins, Operations, Security, Fleet, Monitoring and Bandwidth.
- Added shared 44×44 touch-target floor for primary action controls where practical.
- Added visible `:focus-visible` treatment and reduced-motion support.
- Bounded dialogs to the dynamic viewport with internal scrolling and safer short-screen footer/header behavior.
- Hardened Operations, Fleet, Monitoring and Bandwidth page families for narrow viewports.
- Added safer table scrolling, long-text wrapping and page-level horizontal-overflow guards.
- Improved row-actions dropdown with ARIA menu semantics, Escape handling, focus return and viewport-edge positioning.
- Added Persian RTL and English LTR browser responsive smoke coverage.
- ESLint now passes with zero errors and warnings; stale unused imports/dead dashboard code and service-worker lint defects were cleaned without changing intended behavior.

### Quality and release governance
- Added root `AGENTS.md` with a permanent rule that Production is live and under load and must be changed only through backup/check, narrow mutation, minimal restart, health verification and rollback readiness.
- Added stable `PVN-xxx` task IDs and a detailed numbered feature backlog.
- Added competitor-gap matrix for Marzban, 3X-UI, Hiddify Manager, Remnawave, OpenVPN Access Server and Pritunl capability families.
- Added PVNetwork design-system, UX audit and blocking release QA gate.
- Expanded CI with unit/governance tests, backend/Python compile checks, production frontend build, runtime dependency audit, bundle-size budget, JSON validation and public/private-material guard.
- Added Chromium responsive smoke matrix across all major Main Admin routes and representative mobile/tablet/desktop widths.

### Documentation
- Added Persian and English responsive/accessibility visual guides with sanitized screenshots and Mermaid workflow diagrams.
- Reorganized the roadmap around UX hardening, user lifecycle/observability, enterprise access and optional future universal-protocol work.
- Added `docs/RELEASE-NOTES-v1.0.1.md`.

### Compatibility
- Renewal behavior from v1.0.0 is unchanged.
- No database migration is required by the v1.0.1 UI/governance changes.
- No intended changes to Production firewall, default routes, tunnels or unrelated services.

## 1.0.0 — 2026-09-19

First stable public baseline of PVNetwork.

### User lifecycle
- Expired-user renewal without delete/recreate.
- Unlimited renewal with a fresh 30-day period.
- Finite renewal modes: preserve usage, reset usage or add traffic.
- Mirza renewal integration and regression tests.
- AnyConnect lifecycle kept on the same user identity.

### Operations
- Multi-node assignment, health and realtime traffic monitoring.
- Fleet maintenance, drain/resume and controlled upgrade/retry workflows.
- Bulk operations, transfer/rebalance and usage-history tooling.
- Emergency/canary bandwidth-policy controls.
- Verified manual backup and guarded restore workflow.

### Security and documentation
- Rate limiting, IP allowlist, TOTP 2FA and scoped API tokens.
- English and Persian README files.
- Sanitized screenshots for all major pages and core workflows.
- Full English/Persian visual UI guides.
- Public release source excludes production credentials, databases, profiles and private operational identifiers.
