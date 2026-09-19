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
