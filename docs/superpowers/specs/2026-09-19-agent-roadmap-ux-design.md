# PVNetwork Agent Roadmap & UX Governance Design

**Date:** 2026-09-19  
**Status:** Proposed for user review  
**Target:** post-v1.0.0 development workflow

## 1. Purpose

PVNetwork needs one durable source of truth that survives chat/session changes and tells every future agent exactly what exists, what is missing, what is next, and what qualifies as complete.

The primary control file will be `AGENTS.md`. It will contain a numbered, permanent task registry using stable `PVN-xxx` IDs. `ROADMAP.md` remains the public high-level release roadmap, while detailed execution state lives in `AGENTS.md`.

This design also makes UI/UX quality, responsive behavior, accessibility, regression safety, public-repository privacy, and production safety mandatory completion gates rather than optional polish.
## 2. Core principles

1. Every backlog item has one permanent numeric ID such as `PVN-214`.
2. IDs are never renumbered or reused after assignment.
3. Completed work changes from `[ ]` to `[x]` only after its Definition of Done passes.
4. Every completed item records target/released version, commit, tests and any migration note.
5. Every user-visible change must pass responsive and accessibility checks.
6. Every production-visible change requires backup/check, narrow deployment, health verification and rollback readiness.
7. Every public-repository change must remain sanitized: no production IPs, domains, credentials, user data, certificates, `.ovpn`, DB files or private screenshots.
8. Released tags and assets remain immutable; new behavior ships in a new version.
9. Competitor features are backlog inputs, not automatic requirements: they are evaluated for PVNetwork fit before implementation.
10. After each completed task, the agent reports the exact `PVN-xxx` number to the user.
## 3. Competitor-gap completeness rule

`AGENTS.md` must include every material capability gap found during comparison with the current public capabilities of:

- Marzban
- 3X-UI
- Hiddify Manager
- Remnawave
- OpenVPN Access Server
- Pritunl
- other relevant OpenVPN/Xray/WireGuard control planes discovered later

The comparison is maintained as a source-to-task matrix. Each external capability is marked as one of: `Already present`, `Gap`, `Not applicable`, `Deferred`, or `Rejected with reason`.

A gap cannot remain only in prose. If it is applicable, it receives a stable `PVN-xxx` task ID. This prevents features discovered in research from disappearing between chats.
## 4. Gap families that must be represented

The initial task registry must explicitly cover these comparison-derived families:

- user lifecycle: scheduled renewal, periodic traffic reset, expiry/quota thresholds, self-service lifecycle
- device/session control: device inventory, revoke, HWID/device limits, session inspection
- subscription delivery: QR, Base64, Xray JSON, Sing-box, Clash/Mihomo, template editor, response rules, User-Agent negotiation
- protocols: WireGuard, Xray, VLESS, VMess, Trojan, Shadowsocks, REALITY, Hysteria2, TUIC, Sing-box
- routing/outbounds: WARP, custom outbound pools, chaining, load balancing, failover, GeoIP/GeoSite, split tunnel, per-user/group destination policy
- node abstractions: host abstraction, reusable config profiles, node capability negotiation, admission/capacity policy
- observability: Prometheus, Grafana, long-term node/user history, top users/nodes, central logs, protocol-aware analytics
- enterprise identity: granular RBAC, OAuth/OIDC, Passkey/WebAuthn, LDAP, RADIUS, SAML, group policy
- resilience: control-plane HA, PostgreSQL HA guidance, disaster-recovery test, retry queue, background jobs
- automation/integration: management Telegram bot, generic webhooks, billing/provisioning templates, import/export and migration tools
- installation/operations: one-command install, doctor, update, backup, rollback, migration verification, fresh-node E2E testing
## 5. Source-specific comparison seeds

The first registry generation must preserve the comparison seeds already identified:

- **Marzban:** periodic traffic reset, multi-protocol user identity, QR/subscription outputs, Telegram management, configurable Xray behavior.
- **3X-UI:** broad protocol coverage, REALITY, WARP/outbounds, load balancing, HWID limits, scheduled renewal, multi-format subscriptions, routing controls and PWA-style administration.
- **Hiddify Manager:** easy install/update/backup flows, smart client configuration, domain/CDN/WARP workflows, user-facing connection page.
- **Remnawave:** Host abstraction, Config Profiles, Prometheus, HWID inspection, subscription templates/response rules, passkeys, branding and infrastructure analytics.
- **OpenVPN Access Server:** LDAP, RADIUS, SAML, TOTP, group policy/access control and clustering-oriented enterprise deployment.
- **Pritunl:** organizations/groups, SSO, auditability, route policy and WireGuard support.

These are research inputs. The agent must verify current upstream capabilities before implementing or claiming parity.
## 6. Stable ID ranges

The registry uses ranges so future work stays readable without renumbering:

- `PVN-001..099` — released baseline, critical fixes and compatibility
- `PVN-100..199` — UI/UX, responsive design, accessibility and frontend quality
- `PVN-200..299` — users, subscription lifecycle, devices and reseller workflows
- `PVN-300..399` — nodes, fleet, routing, capacity and network operations
- `PVN-400..499` — monitoring, analytics, logs, reports and notifications
- `PVN-500..599` — security, RBAC, enterprise identity and audit
- `PVN-600..699` — API, Mirza, bots, webhooks, billing and automation
- `PVN-700..799` — protocols, Xray/WireGuard/Sing-box and subscription formats
- `PVN-800..899` — install, update, backup, rollback, CI/CD, HA and disaster recovery
- `PVN-900..999` — migrations, ecosystem compatibility and approved experimental work

A task keeps its number forever, including after completion, rejection or supersession.
## 7. Task record format

Each item in `AGENTS.md` uses the same compact schema:

```text
PVN-142 [ ] Responsive Renew modal
Area: UX / User Lifecycle
Target: v1.1.0
Depends: PVN-105, PVN-107
Source gap: internal + responsive audit
Acceptance: no clipping/overflow at required widths; keyboard/touch usable
Tests: component + responsive smoke + regression
Status: OPEN
```

On completion the agent changes `[ ]` to `[x]`, records the commit and released/target version, and reports `PVN-142` to the user. Rejected work remains in the registry with `Status: REJECTED` and a reason instead of being deleted.
## 8. Definition of Done

A task is not complete merely because code exists. `[x]` requires all applicable gates:

1. implementation matches the task acceptance criteria;
2. focused automated tests pass;
3. relevant regression suite passes;
4. frontend production build / backend compile checks pass where applicable;
5. user-visible changes pass the responsive matrix;
6. interaction changes pass mouse, touch and keyboard checks;
7. Persian RTL and English LTR remain usable;
8. dark/light modes remain readable where supported;
9. loading, empty, success and error states are reachable and understandable;
10. production deployment, if any, has backup/check, narrow restart, health verification and rollback path;
11. public GitHub content is sanitized;
12. CHANGELOG/docs are updated when behavior is release-visible.
## 9. UI/UX governance

PVNetwork adopts the relevant guidance from UI UX Pro Max as a quality reference, not as an automatic code generator. The mandatory product rules are:

- mobile-first responsive layout;
- no horizontal page scroll at supported widths;
- essential text reflows without clipping;
- touch targets are at least 44×44 px where practical;
- interactive controls never depend on hover alone;
- visible keyboard focus and operable keyboard navigation;
- WCAG-oriented text contrast target of at least 4.5:1 for normal text;
- body text normally 16 px or larger, with readable line-height;
- native/semantic controls and accessible names for icon-only actions;
- `prefers-reduced-motion` respected;
- state is not communicated by color alone;
- destructive actions require clear confirmation and recovery/rollback where feasible;
- loading actions show progress/disabled state and prevent accidental duplicate submission.
## 10. Responsive acceptance matrix

Every page, modal, menu, table and primary workflow must be checked at these representative widths:

- 360 px — small phone
- 375 px — standard phone
- 390 px — common iPhone width
- 430 px — large phone
- 768 px — tablet
- 1024 px — tablet/small desktop
- 1366 px — laptop
- 1440 px — desktop
- 1920 px — full-HD desktop

Browser zoom checks: 100%, 125% and 150% for core admin flows. No required control may become unreachable because of viewport height, safe-area, modal sizing, fixed headers or overflow containers.
## 11. Mobile/table interaction policy

Desktop tables must not simply shrink until text becomes unusable. For narrow screens, each table chooses one documented strategy:

- card/list transformation for row-oriented management;
- priority columns plus a details disclosure;
- controlled internal horizontal scroll only when the data itself is inherently tabular and no action becomes hidden.

Primary row actions must remain reachable by touch. Three-dot menus must fit the viewport, reposition near edges, close predictably, and expose the same actions available on desktop. Modals must scroll internally when necessary and keep confirmation/cancel actions reachable.

Sidebar navigation must have a mobile equivalent. Navigation depth, labels, back behavior and active state must remain understandable in both RTL and LTR layouts.
## 12. Files to create or maintain

- `AGENTS.md` — private-to-project execution contract and numbered master checklist; safe for public repository.
- `ROADMAP.md` — public release-level summary derived from the master checklist.
- `docs/FEATURE-BACKLOG.md` — readable detailed backlog grouped by product area.
- `docs/COMPETITOR-GAP-MATRIX.md` — source panel capability → PVNetwork state → `PVN-xxx` mapping.
- `docs/UX-AUDIT.md` — page/component responsive and accessibility audit status.
- `docs/QA-RELEASE-GATE.md` — release blocking checks.
- `design-system/pvnetwork/MASTER.md` — product-wide UI tokens/patterns/interaction rules.

No file may contain private production credentials, addresses, customer/user data or live secrets.
## 13. Agent operating workflow

At the start of a development task, the agent reads `AGENTS.md`, identifies the requested `PVN-xxx`, checks dependencies and current release state, then works only on the approved scope.

At completion, the agent must:

1. run the task-specific Definition of Done;
2. update the task status and evidence in `AGENTS.md`;
3. update `ROADMAP.md`/docs only when externally relevant;
4. commit with the task ID in the commit context;
5. report the completed task number to the user;
6. state the next recommended open task number without silently starting it.

Large releases may complete multiple IDs, but each ID remains independently traceable.
## 14. Production safety

The master checklist must preserve current production constraints:

- running services and active VPN users are assumed live unless explicitly proven otherwise;
- backup/check before production mutation;
- no blanket firewall flush or default-route replacement;
- unrelated tunnels, databases, x-ui/Xray or host services are preserved;
- restart only the service required by the change;
- database migrations are reviewed and verified before release;
- node changes are canary-tested where practical;
- failed health verification triggers rollback rather than continued mutation;
- public documentation uses sanitized screenshots and example endpoints only.

Documentation-only backlog work must not restart production services.
## 15. Release governance

`v1.0.0` remains frozen. The new master checklist starts post-v1.0.0 work without rewriting released history.

- compatible bug fixes target `1.0.x`;
- compatible feature work targets `1.x.0`;
- breaking protocol/data/interface changes require a major-version decision;
- every production-visible release updates `VERSION`, `CHANGELOG.md`, release notes and GitHub Release;
- release candidates cannot be promoted while blocking `PVN-xxx` QA/security tasks remain open;
- screenshots/docs are refreshed when the visible UI meaningfully changes.

The release gate references task IDs, so a future agent can determine exactly which blockers remain.
## 16. Acceptance criteria for this governance subsystem

The implementation is accepted when:

1. `AGENTS.md` exists and contains the complete initial numbered registry, including the existing 100 roadmap concepts and all known comparison-derived gaps.
2. Every applicable competitor gap maps to an explicit `PVN-xxx` task or a documented rejection/defer decision.
3. UX/responsive/accessibility tasks are first-class numbered work, not a generic single checklist item.
4. `docs/COMPETITOR-GAP-MATRIX.md` links external capability families to PVNetwork state and task IDs.
5. `docs/UX-AUDIT.md` inventories every current main page and core modal/workflow.
6. `docs/QA-RELEASE-GATE.md` prevents `[x]` and release promotion without required evidence.
7. `design-system/pvnetwork/MASTER.md` defines stable design/interaction rules for desktop, tablet and mobile.
8. `ROADMAP.md` remains consistent with the detailed registry.
9. all new documentation passes a public-data scan before push.
10. no production service restart is needed to implement this documentation/governance layer.
## 17. UI/UX reference provenance

Reference project: `nextlevelbuilder/ui-ux-pro-max-skill` (`https://github.com/nextlevelbuilder/ui-ux-pro-max-skill`).

PVNetwork adopts applicable principles from this reference—especially accessibility, touch interaction, responsive layout, typography, forms/feedback, navigation, reduced motion and pre-delivery QA—while keeping PVNetwork's own design system and code architecture authoritative.

No third-party skill output may override production safety, repository privacy, existing user workflows or explicit PVNetwork requirements.
