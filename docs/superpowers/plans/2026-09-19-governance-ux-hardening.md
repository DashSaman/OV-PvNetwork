# Governance & UX Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish a durable agent/task governance system, then harden every current PVNetwork admin UI flow for desktop/mobile accessibility and publish the next documented release without destabilizing live production.

**Architecture:** Work happens on isolated Git branches/workspaces. Documentation/governance is completed first with zero production restarts. UI changes then proceed page-by-page with focused tests, responsive checks, sanitized screenshots, CI, and only after release gates pass may a narrow production deployment occur.

**Tech Stack:** FastAPI/Python 3.12, React/Vite, PostgreSQL/Alembic, systemd/nginx, GitHub Actions, Playwright/browser automation where available.

**Spec:** `docs/superpowers/specs/2026-09-19-agent-roadmap-ux-design.md`

## Global Constraints

- Production services and VPN users are assumed live at all times.
- Never flush a firewall, replace a default route, restart unrelated services, or mutate unrelated tunnels/databases.
- Public GitHub content must contain no live IPs/domains/credentials/user data/certificates/.ovpn/database files/private screenshots.
- All implementation work occurs off `main`; released tags remain immutable.
- A task is `[x]` only after its stated tests and release/UX gates pass.
- User-visible changes require Persian RTL + English LTR, touch, keyboard, dark/light, and responsive verification.

---

### Task 1: Governance source of truth

**Files:** Create `AGENTS.md`, `docs/FEATURE-BACKLOG.md`, `docs/COMPETITOR-GAP-MATRIX.md`, `docs/UX-AUDIT.md`, `docs/QA-RELEASE-GATE.md`, `design-system/pvnetwork/MASTER.md`.

- [ ] Create permanent `PVN-xxx` registry and production-safety contract.
- [ ] Map known competitor gaps to task IDs or explicit N/A/deferred decisions.
- [ ] Add UX/responsive audit matrix for every current page/modal/workflow.
- [ ] Add release-blocking QA rules and design-system rules.
- [ ] Run public-data/secret scan and markdown consistency checks.
- [ ] Commit and push governance artifacts.

### Task 2: Baseline automated UX tests

**Files:** Create frontend test/e2e configuration and responsive smoke tests without touching production.

- [ ] Add tests that enumerate current routes and core modals.
- [ ] Add viewport checks for 360, 375, 390, 430, 768, 1024, 1366, 1440 and 1920 px.
- [ ] Assert no page-level horizontal overflow and no unreachable primary controls.
- [ ] Add keyboard/focus and accessible-name smoke checks for primary navigation/actions.
- [ ] Run existing renewal tests + frontend production build + backend compile.
- [ ] Commit test baseline.

### Task 3: Navigation and shell hardening

**Files:** `frontend/src/pages/DashboardLayout.jsx`, `frontend/src/components/Sidebar.jsx`, `frontend/src/components/MobileNav.jsx`, shared CSS.

- [ ] Make every admin section reachable on phone/tablet/desktop.
- [ ] Preserve active state, predictable close/back behavior, RTL/LTR placement and keyboard operation.
- [ ] Ensure touch targets and focus visibility meet the project gate.
- [ ] Run viewport/navigation tests and production build.
- [ ] Commit with matching `PVN-1xx` evidence.

### Task 4: Users and lifecycle UX

**Files:** User management/table, Add/Edit/Renew/AnyConnect/download/domain-history modals and CSS.

- [ ] Replace unusable narrow tables with documented responsive strategy.
- [ ] Keep actions reachable by touch; dropdown must stay within viewport.
- [ ] Make forms/modals scroll safely with cancel/confirm always reachable.
- [ ] Verify finite/unlimited renewal and unlimited reset regression tests.
- [ ] Run RTL/LTR, keyboard, 360–1920 viewport tests and build.
- [ ] Commit evidence to `AGENTS.md` and UX audit.

### Task 5: Nodes, admins, operations, fleet, monitoring, security and bandwidth UX

- [ ] Harden each current page and its modals/actions one page at a time.
- [ ] Preserve operational meaning; do not change backend/network behavior merely for visual cleanup.
- [ ] Add loading/empty/error/confirmation states where missing.
- [ ] Run responsive/accessibility smoke tests after each page group.
- [ ] Commit each independently reviewable group with PVN IDs.

### Task 6: Full regression and sanitized visual documentation

- [ ] Run focused tests, full available test suite, Python compile, frontend build and lint report.
- [ ] Capture sanitized screenshots at desktop and mobile widths using demo/masked data only.
- [ ] Refresh `README.md`, `README.fa.md`, `docs/UI-GUIDE.md`, `docs/UI-GUIDE.fa.md`.
- [ ] Update completed task evidence in `AGENTS.md`, `UX-AUDIT.md`, `CHANGELOG.md` and release notes.
- [ ] Run repository secret/identifier scan before push.

### Task 7: Release and controlled production rollout

- [ ] Verify CI green on release commit.
- [ ] Create production backup/check before any mutation.
- [ ] Apply only the release files required; restart only `ov-panel.service` if deployment needs it.
- [ ] Verify local/public HTTP, OpenAPI, service errors and critical user/node flows.
- [ ] Roll back immediately if health verification fails.
- [ ] Publish new immutable GitHub tag/release with sanitized artifacts and SHA256.
- [ ] Record release version/commit in all completed `PVN-xxx` items.