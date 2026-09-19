# PVNetwork Governance and UX Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish a production-safe agent contract and ship a responsive/accessibility hardening release with bilingual illustrated documentation without disrupting live services.

**Architecture:** Work entirely from an isolated Git branch/worktree. Governance files are documentation-only and never restart Production. UI changes stay in frontend source and tests until release gates pass. Production deployment, if required, uses backup/check, minimal restart, health verification and rollback readiness.

**Tech Stack:** React 19, Vite 7, CSS, FastAPI/Python 3.12, GitHub Actions, Playwright/automated smoke tests where practical.

**Spec:** `docs/superpowers/specs/2026-09-19-agent-roadmap-ux-design.md`

## Global Constraints

- Production is live and under load; assume all services and user sessions matter.
- No blanket firewall flush, default-route replacement, unrelated service restart or destructive DB operation.
- Public repository content must be sanitized.
- `v1.0.0` remains immutable; this work targets `v1.1.0` unless a blocker forces a patch-only release.
- Every completed task records a stable `PVN-xxx` ID and evidence.
- User-visible flows must remain usable at 360/375/390/430/768/1024/1366/1440/1920 px and 100/125/150% zoom.

---

### Task 1: Persist agent safety and backlog governance

**Files:**
- Create: `AGENTS.md`
- Create: `docs/FEATURE-BACKLOG.md`
- Create: `docs/COMPETITOR-GAP-MATRIX.md`
- Create: `docs/QA-RELEASE-GATE.md`
- Modify: `ROADMAP.md`

- [ ] **Step 1:** Add the live-production warning and mandatory agent workflow to `AGENTS.md`.
- [ ] **Step 2:** Add stable task ranges and map known competitor gaps to numbered `PVN-xxx` IDs.
- [ ] **Step 3:** Create the competitor matrix covering Marzban, 3X-UI, Hiddify, Remnawave, OpenVPN Access Server and Pritunl.
- [ ] **Step 4:** Add release blockers and Definition of Done to `docs/QA-RELEASE-GATE.md`.
- [ ] **Step 5:** Run public-data/secret grep and Markdown link/path checks.
- [ ] **Step 6:** Commit with message `docs: establish production-safe agent governance`.

### Task 2: Persist design system and UX audit

**Files:**
- Create: `design-system/pvnetwork/MASTER.md`
- Create: `docs/UX-AUDIT.md`
- Reference: `frontend/src/index.css`
- Reference: `frontend/src/pages/*.jsx`
- Reference: `frontend/src/components/*.jsx`

- [ ] **Step 1:** Define spacing, typography, color, focus, touch, modal, table, navigation, RTL/LTR and responsive rules.
- [ ] **Step 2:** Inventory every current main page and core modal/workflow.
- [ ] **Step 3:** Record current status at every required breakpoint and interaction mode.
- [ ] **Step 4:** Mark each concrete gap with its `PVN-xxx` ID.
- [ ] **Step 5:** Commit with message `docs: define PVNetwork design system and UX audit`.

### Task 3: Add automated frontend release gates

**Files:**
- Modify: `.github/workflows/ci.yml`
- Create: `tests/test_ui_governance.py`
- Create: `frontend/tests/responsive-smoke.spec.js` if Playwright is available in project test dependencies; otherwise add a dependency-neutral source smoke gate and keep browser automation as an open task.

- [ ] **Step 1:** Write failing tests asserting required responsive/accessibility source contracts.
- [ ] **Step 2:** Run tests and confirm RED before implementation.
- [ ] **Step 3:** Extend CI to run renewal tests, Python compile, frontend production build and governance/secret checks.
- [ ] **Step 4:** Run CI-equivalent commands locally in isolated workspace.
- [ ] **Step 5:** Commit with message `test: add v1.1 UI and governance release gates`.

### Task 4: Harden global responsive/accessibility primitives

**Files:**
- Modify: `frontend/src/index.css`
- Modify: `frontend/src/components/ActionsDropdown.jsx`
- Modify: modal components only where semantic/focus fixes cannot be solved globally.
- Test: `tests/test_ui_governance.py`

- [ ] **Step 1:** Add failing source-level tests for minimum touch target, focus-visible, reduced motion, modal max-height/overflow, responsive controls and no page-level overflow.
- [ ] **Step 2:** Run tests and confirm failures.
- [ ] **Step 3:** Implement minimal global CSS and dropdown semantics/labels without changing business logic.
- [ ] **Step 4:** Build frontend and run regression tests.
- [ ] **Step 5:** Commit with message `feat: harden global responsive and accessible UI primitives`.

### Task 5: Harden page families incrementally

**Files:**
- Modify as needed: `DashboardHome.jsx`, `UserManagement.jsx`, `NodeManagement.jsx`, `AdminManagement.jsx`, `OperationsCenter.jsx`, `SecuritySettings.jsx`, `FleetManagement.jsx`, `MonitoringSettings.jsx`, `BandwidthControl.jsx`, `LoginPage.jsx`, subscription template and associated CSS.

- [ ] **Step 1:** Users + Renew/AnyConnect/Add/Edit flows; test/build; commit.
- [ ] **Step 2:** Nodes + Add/Edit/download flows; test/build; commit.
- [ ] **Step 3:** Admins + reseller flows; test/build; commit.
- [ ] **Step 4:** Operations + backup/restore; test/build; commit.
- [ ] **Step 5:** Security + Fleet + Monitoring + Bandwidth; test/build; commit.
- [ ] **Step 6:** Dashboard + Login + Subscription page; test/build; commit.
- [ ] **Step 7:** Update `docs/UX-AUDIT.md` evidence for every page.

### Task 6: Bilingual illustrated documentation refresh

**Files:**
- Modify: `README.md`
- Modify: `README.fa.md`
- Modify: `docs/UI-GUIDE.md`
- Modify: `docs/UI-GUIDE.fa.md`
- Add/replace: `docs/images/ui/*` with sanitized screenshots only.

- [ ] **Step 1:** Capture sanitized desktop and mobile views for all main sections and changed workflows.
- [ ] **Step 2:** Verify images contain no live user, IP, domain, secret, token, UUID or Production-specific data.
- [ ] **Step 3:** Update English documentation and button/workflow explanations.
- [ ] **Step 4:** Update Persian documentation with the same coverage.
- [ ] **Step 5:** Verify all image and document links.
- [ ] **Step 6:** Commit with message `docs: refresh bilingual illustrated v1.1 guide`.

### Task 7: Final release verification and v1.1.0 publication

**Files:**
- Modify: `VERSION`
- Modify: `CHANGELOG.md`
- Create: `docs/RELEASE-NOTES-v1.1.0.md`
- Update: `AGENTS.md`, `ROADMAP.md`, `docs/QA-RELEASE-GATE.md`

- [ ] **Step 1:** Run all focused tests, renewal regression, Python compile and frontend production build.
- [ ] **Step 2:** Run responsive/accessibility release gates and public-data/secret scans.
- [ ] **Step 3:** Verify Production read-only health before any deployment.
- [ ] **Step 4:** If deploying UI to Production, take backup, deploy only required files/build, restart only `pvnetwork-panel`, and verify local/public health; rollback on failure.
- [ ] **Step 5:** Capture final sanitized screenshots from the verified release build.
- [ ] **Step 6:** Update task evidence and version/changelog/release notes.
- [ ] **Step 7:** Merge/push the verified branch, tag `v1.1.0`, create GitHub Release and attach sanitized source artifact + SHA256.
- [ ] **Step 8:** Verify the GitHub Release is published, not draft/prerelease, and README images render from `main`.

## Self-review

- Spec coverage: governance, competitor gaps, UX, testing, docs, Production safety and release publication are mapped above.
- Placeholder scan: no implementation placeholder is permitted; unresolved browser automation remains an explicit conditional branch rather than a hidden assumption.
- Scope: backend feature backlog is documented but not silently implemented in the UX hardening release; only approved v1.1 blockers are shipped now.
