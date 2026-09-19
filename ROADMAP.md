# PVNetwork Panel Roadmap

This roadmap keeps released tags immutable. Detailed permanent task IDs live in `AGENTS.md` and `docs/FEATURE-BACKLOG.md`.

## v1.0.0 — released stable baseline

- Expired/unlimited user renewal without delete/recreate.
- Finite renewal modes: preserve, reset and add traffic.
- Renewal support in Mirza integration.
- Unlimited Reset Usage starts a new 30-day period.
- Multi-node OpenVPN, AnyConnect integration, fleet, operations, bandwidth, monitoring and security foundations.
- Sanitized public source, bilingual illustrated docs, release artifact and SHA256.

## v1.1.0 — UI/UX, responsive and project-governance hardening

Release goal: make every existing panel area consistently usable on desktop, tablet and phone before adding another large feature family.

- Persistent Production-safety and Agent execution contract.
- Numbered `PVN-xxx` backlog and competitor-gap matrix.
- Design-system and blocking QA/release gate.
- Responsive hardening at 360–1920 px plus 125%/150% zoom checks.
- Touch-target, keyboard, focus, reduced-motion and contrast hardening.
- Persian RTL and English LTR audits.
- Mobile-safe action menus, tables, dialogs, search/sort/pagination and fixed navigation.
- Loading/empty/error/retry and duplicate-submit consistency.
- Automated governance/UI smoke tests and stronger CI/secret guards.
- Refreshed sanitized Persian/English illustrated documentation.
- New `v1.1.0` GitHub Release only after all mandatory release gates pass.

Primary blockers: `PVN-100..139` plus all applicable items in `docs/QA-RELEASE-GATE.md`.

## v1.2.x — user lifecycle, devices, observability and automation

- Periodic traffic reset and scheduled renewal.
- Multi-stage expiry and traffic-threshold notifications.
- Generic signed webhooks and resilient background/retry jobs.
- Prometheus/Grafana and long-term node/user traffic history.
- Top users/nodes analytics and CSV/Excel/PDF reporting.
- Device inventory, session revoke and HWID/device limits.
- Self-service portal and QR connection outputs.
- Node capacity/admission/failover and richer assignment policies.
- Management Telegram bot and expanded Mirza lifecycle parity.
- Import/export and migration foundations.

Detailed tasks: `PVN-200..499` and `PVN-600..699`.

## v1.3.x — enterprise identity, policy, HA and operations

- Granular RBAC/custom roles.
- OAuth2/OIDC and Passkey/WebAuthn.
- LDAP, RADIUS and SAML SSO.
- Certificate/TLS management and renewal visibility.
- Split-tunnel, destination and GeoIP/GeoSite policy management.
- Control-plane/PostgreSQL/reverse-proxy HA guides and tested DR workflow.
- Installer/update/backup/rollback hardening, signed artifacts, SBOM and compatibility matrices.

Detailed tasks: `PVN-500..599` and `PVN-800..899`.

## v2.0 — optional universal VPN/proxy control plane

Subject to explicit architecture approval after the OpenVPN/AnyConnect line is stable:

- WireGuard and Xray cores.
- VLESS, VMess, Trojan, Shadowsocks, REALITY, Hysteria2, TUIC and Sing-box.
- Multi-protocol user identity and protocol-aware quota/session accounting.
- Base64/Xray JSON/Sing-box/Clash-Mihomo subscriptions and User-Agent negotiation.
- Subscription template editor/response rules.
- WARP, custom outbound pools, chaining, load balancing and failover.
- Host abstraction, reusable config profiles and protocol capability negotiation.
- Migration assistants and client compatibility suites.

Detailed tasks: `PVN-700..799` and `PVN-900..999`.

## Release rule

Every Production-visible behavior change gets a version, changelog entry and tagged GitHub Release. Existing tags/assets are immutable. No release is promoted while its blocking `PVN-xxx` QA/security tasks remain open or Production-health verification is unresolved.
