# PVNetwork Panel v1.0.0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver PVNetwork Panel v1.0.0 as a safe, documented, reproducible stable release with expired-user renewal and release tooling.

**Architecture:** Keep the current production control-plane and node protocol backwards-compatible. Add renewal as a first-class backend operation, expose it through the existing UI and Mirza integration, then package operational tooling and documentation around the verified production baseline. Release work happens on `release/v1.0.0-baseline`; production changes are applied only after backups and local verification.

**Tech Stack:** FastAPI, SQLAlchemy/PostgreSQL, React/Vite, OpenVPN node agents, systemd, nginx, bash, GitHub Releases.

**Spec:** `docs/superpowers/specs/2026-09-18-v1-release-baseline-design.md`

## Global Constraints
- Preserve UUID, username, node assignments, subscription URL, and AnyConnect identity during renewal.
- Never publish production secrets/customer data.
- Never flush or wholesale-replace firewall/routing rules.
- Keep legacy internal paths/service names when renaming would risk v1.0.0 compatibility.
- Require backup plus fresh build/compile/health/regression evidence before release.

---

### Task 1: Renewal domain behavior
**Files:** modify user/Mirza routers and schemas; add focused regression tests.
- [ ] Write failing tests for expired unlimited renewal, finite renewal, traffic reset/add, node sync, and identity preservation.
- [ ] Run tests and confirm failures are caused by missing renewal behavior.
- [ ] Implement one transactional renewal service used by UI API and Mirza.
- [ ] Verify tests pass and compile backend.
- [ ] Commit `feat: add safe expired-user renewal`.

### Task 2: Renewal UI
**Files:** user actions/modal/table translations.
- [ ] Add failing UI-level assertions/smoke checks for Renew action visibility on expired users.
- [ ] Add Renew modal with 30/60/90/custom expiry plus finite-plan traffic options.
- [ ] Build frontend and verify existing actions remain intact.
- [ ] Commit `feat: add user renewal workflow`.

### Task 3: Release/operations tooling
**Files:** `scripts/install-panel.sh`, `scripts/install-node.sh`, `scripts/pvnetwork`, release helpers.
- [ ] Add shell/static tests for safe defaults, idempotency markers, backup-first behavior, and no firewall flush.
- [ ] Implement panel/node install, doctor, update, backup, rollback, version commands.
- [ ] Run shell checks and dry-run tests.
- [ ] Commit `feat: add production release tooling`.

### Task 4: Bilingual documentation and visuals
**Files:** README.md, README.fa.md, docs/*.md, docs/images/*.
- [ ] Inventory every visible page/action from production source.
- [ ] Generate sanitized screenshots or diagrams with numbered callouts.
- [ ] Document install, node install, update, backup, rollback, admin/user guides in English and Persian.
- [ ] Verify all links/image paths and that no secrets appear.
- [ ] Commit `docs: add bilingual illustrated documentation`.

### Task 5: Competitive matrix and roadmap
**Files:** `docs/FEATURE-MATRIX.md`, `ROADMAP.md`.
- [ ] Compare PVNetwork Panel with Marzban, 3x-ui, Hiddify, Remnawave, OpenVPN Access Server, and Pritunl using current upstream documentation.
- [ ] Separate current strengths, core gaps, and optional universal-protocol expansion.
- [ ] Number all missing features and create GitHub issues grouped by target release.
- [ ] Commit `docs: add competitive roadmap`.

### Task 6: Stable release packaging
**Files:** VERSION, CHANGELOG.md, release notes, release archive/checksums.
- [ ] Set version to 1.0.0 and document compatibility/known issues.
- [ ] Run backend compile/tests, frontend build, health checks, renewal regression, and installer dry-runs.
- [ ] Create sanitized source archive and SHA256 checksums.
- [ ] Merge/release only after all gates pass.
- [ ] Tag and publish GitHub Release `v1.0.0` with artifacts and upgrade/rollback notes.