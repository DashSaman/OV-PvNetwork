# Changelog

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
- Corrected the browser-test language key to the real `ovpanel_language`, so RTL/LTR checks now exercise the actual application language.
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

First stable public baseline of OV-PvNetwork.

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
