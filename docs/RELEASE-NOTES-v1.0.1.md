# PVNetwork Panel v1.0.1 — Release Notes

Status: release candidate documentation. Publish only after `docs/QA-RELEASE-GATE.md` is fully satisfied.

## Focus

v1.0.1 is a compatibility-preserving UI/UX and project-governance release. It does not replace the OpenVPN/AnyConnect data model or intentionally change existing Production routing/firewall behavior.

## Monitoring improvements

- Optional Telegram node status alerts now send `🔴 Node DOWN` when a node becomes offline and `🟢 Node UP` after recovery.
- The node-status alert toggle is enabled by default to preserve the existing down-alert behavior while making recovery explicit.
- Repeated unchanged states are deduplicated through the monitor state file.

## UI/UX improvements

- Complete Main Admin mobile navigation: Dashboard, Users, Nodes plus a **More** menu for Admins, Operations, Security, Fleet, Monitoring and Bandwidth.
- Shared 44×44 touch-target floor for primary interactive controls where practical.
- Visible keyboard `:focus-visible` treatment.
- Reduced-motion support via `prefers-reduced-motion`.
- Viewport-bounded, internally scrollable modal behavior for short phone screens.
- Safer fixed-mobile-navigation spacing using safe-area insets.
- Responsive wrapping/stacking for Operations, Fleet, Monitoring and Bandwidth page families.
- Page-level horizontal-overflow guard and bounded table scrolling.
- Accessible row-actions dropdown semantics, Escape close and focus return.
- Better long-text wrapping for translated labels, usernames, domains and operational output.

## Quality and governance

- New root `AGENTS.md` permanently records that Production is live and under load and defines mandatory backup/check, minimal-change and health-verification rules.
- Stable `PVN-xxx` task registry with a large capability backlog and permanent IDs.
- Competitor-gap matrix covering Marzban, 3X-UI, Hiddify Manager, Remnawave, OpenVPN Access Server and Pritunl capability families.
- Product-wide PVNetwork design-system document.
- Blocking release QA checklist and explicit UX audit matrix.
- CI now runs Python/backend compilation, all unit/governance tests, frontend production build, JSON validation and public/private-material guards.
- Chromium responsive smoke matrix covers all major Main Admin routes at 360, 375, 390, 430, 768, 1024, 1366, 1440 and 1920 px.
- Frontend ESLint is clean with 0 errors and 0 warnings.
- Sanitized v1.0.1 screenshot evidence includes desktop/mobile captures for English and Persian route families.

## Documentation

- Persian and English responsive/accessibility guides with sanitized screenshots and visual workflow diagrams.
- Existing illustrated UI guides remain the page-by-page reference.
- Roadmap reorganized around UX hardening, user lifecycle/observability, enterprise controls and optional future universal-protocol work.

## Compatibility

- Existing user identities, UUIDs, node assignments and renewal behavior remain unchanged by this UI release.
- Existing AnyConnect behavior is not intentionally changed.
- No database migration is required by the UI/governance changes in this release candidate.
- Existing `v1.0.0` release/tag remains immutable.

## Upgrade safety

Production is assumed live. Do not replace the live tree blindly.

1. Verify current health.
2. Take a backup/snapshot appropriate to the deployment.
3. Apply only the verified v1.0.1 release tree/build.
4. Restart only the required `pvnetwork-panel` service.
5. Verify local/public panel health and critical user/node workflows.
6. Roll back immediately if verification fails.

Do not flush firewalls, replace default routes, recreate working nodes, rotate valid certificates, or alter unrelated tunnels/services for this release.

## Validation required before publication

- Unit/regression tests PASS.
- Python compile PASS.
- Frontend production build PASS.
- Chromium responsive smoke matrix PASS.
- Public/private-material scan PASS.
- Persian/English documentation paths PASS.
- Production pre-deploy backup/check recorded.
- Production local/public health PASS after deployment, if deployment is included.
- Release artifact and SHA256 verified.

## Known scope boundaries

The numbered backlog includes WireGuard, Xray, additional protocols, Prometheus/Grafana, advanced enterprise SSO and lifecycle automation, but those are future tasks. Their presence in the backlog does not imply they are included in v1.0.1.

## Production verification

- Verified pre-deploy backup with restore test: PASS.
- Alembic advanced from `c1d2e3f4a5b6` to `c2d3e4f5a6b7` transactionally.
- Only the PVNetwork panel service was restarted; unrelated VPN/tunnel/database services were not restarted.
- Local panel HTTP: 200.
- Public panel HTTP: 200.
- `pvnetwork-panel.service`: active/enabled.
- `pvnetwork-panel-monitor.timer`: active; first post-deploy run exited `0/SUCCESS`.
- Monitoring migration default: node online/offline alerts enabled.
