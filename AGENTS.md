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

## Definition of Done

A task is DONE only when all applicable gates pass: acceptance criteria; focused tests; regression tests; frontend production build/backend compile; responsive matrix; accessibility/touch/keyboard checks; RTL/LTR; light/dark; loading/empty/error states; backup and rollback readiness for Production; sanitized public repository; changelog/docs; final health check.

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

## v1.1.0 blocking UX/quality tasks

- PVN-100 [ ] Mobile navigation redesign.
- PVN-101 [ ] Responsive Users page.
- PVN-102 [ ] Responsive Nodes page.
- PVN-103 [ ] Responsive Admins page.
- PVN-104 [ ] Responsive Operations page.
- PVN-105 [ ] Responsive Security page.
- PVN-106 [ ] Responsive Fleet page.
- PVN-107 [ ] Responsive Monitoring page.
- PVN-108 [ ] Responsive Bandwidth page.
- PVN-109 [ ] Responsive Dashboard.
- PVN-110 [ ] Responsive Login page.
- PVN-111 [ ] Responsive Subscription page.
- PVN-112 [ ] Mobile-friendly action menus.
- PVN-113 [ ] 44×44 touch target audit.
- PVN-114 [ ] No page-level horizontal overflow.
- PVN-115 [ ] Persian RTL full audit.
- PVN-116 [ ] English LTR full audit.
- PVN-117 [ ] Keyboard-only navigation audit.
- PVN-118 [ ] Visible focus states.
- PVN-119 [ ] Accessible icon-only controls.
- PVN-120 [ ] WCAG contrast audit.
- PVN-121 [ ] Reduced-motion support.
- PVN-122 [ ] Modal viewport containment and internal scrolling.
- PVN-123 [ ] Mobile table/card strategy for management screens.
- PVN-124 [ ] Responsive pagination/search/sort controls.
- PVN-125 [ ] Loading, empty, error and retry states.
- PVN-126 [ ] Duplicate-submit prevention and mutation feedback.
- PVN-127 [ ] Responsive Renew modal.
- PVN-128 [ ] Responsive AnyConnect modal.
- PVN-129 [ ] Responsive Add/Edit User flows.
- PVN-130 [ ] Responsive Add/Edit Node flows.
- PVN-131 [ ] Responsive Add/Edit Admin flows.
- PVN-132 [ ] Responsive Backup/Restore panel.
- PVN-133 [ ] Responsive Domain History/Download dialogs.
- PVN-134 [ ] Playwright responsive smoke baseline.
- PVN-135 [ ] Accessibility smoke baseline.
- PVN-136 [ ] Desktop/mobile visual-regression baseline.
- PVN-137 [ ] Frontend bundle-size budget.
- PVN-138 [ ] Long-translation/clipped-text stress test.
- PVN-139 [ ] Persian/English typography rendering audit.

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
Release: v1.1.0
Commit: <sha>
Tests: <exact commands/results>
Docs: <paths>
Production: HEALTH=PASS or N/A
```

## Release rule

`v1.0.0` is frozen. Compatible feature work targets `v1.1.0`; compatible fixes may use `1.0.x`; breaking protocol/data/interface changes require a major-version decision. `v1.1.0` cannot be published while its release-gate blockers remain open.