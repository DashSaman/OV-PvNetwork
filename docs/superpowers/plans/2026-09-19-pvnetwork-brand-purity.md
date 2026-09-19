# PVNetwork Brand Purity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Remove every former upstream panel identifier from the tracked PVNetwork tree and migrate runtime naming to PVNetwork-owned paths/services without breaking Production.

**Architecture:** Add a permanent source-brand guard first, then rename package/runtime/UI/storage/backup identifiers consistently. Preserve MIT attribution without retaining the former product name. Release as v1.0.4, deploy to a parallel PVNetwork runtime path/service, verify it, switch traffic safely, then retire the legacy runtime name.

**Tech Stack:** Python/FastAPI, React/Vite, Bash/systemd/nginx, PostgreSQL, GitHub Actions.

**Spec:** AGENTS.md owner requirements + this plan.

## Global Constraints
- Tracked source tree must contain zero former upstream panel identifiers in dashed, underscored, spaced, or concatenated forms.
- Product name is PVNetwork Panel / Private Network; runtime path is `/opt/pvnetwork-panel`; service is `pvnetwork-panel.service`.
- Production mutation requires verified backup, rollback path, narrow deployment, local/public health, and integration/log checks.
- No firewall/default-route/tunnel/node/certificate changes.
- Preserve upstream MIT copyright attribution without the former product brand.

## Review Focus
- Installer/update lifecycle resolves DashSaman/OV-PvNetwork releases, not upstream releases.
- Existing PostgreSQL Production data remains unchanged.
- UI asset base path remains the live configured URL path.
- Backup/restore paths and helper commands are renamed consistently.
- Language persistence uses the new PVNetwork-owned storage key.

---

### Task 1: Permanent brand guard
- [x] Add a failing test that scans tracked paths/content for forbidden former-brand forms.
- [x] Run it and record RED against the current tree.
- [x] Add PVN-025/v1.0.4 and the zero-legacy-name rule to AGENTS.md without spelling the forbidden token.

### Task 2: Source/runtime rename
- [x] Rename runtime/service/config/package/UI/storage/backup identifiers to PVNetwork equivalents.
- [x] Switch installer release source to DashSaman/OV-PvNetwork.
- [x] Preserve MIT copyright attribution while removing the former product brand.
- [x] Run focused guard GREEN, full unit/governance suite, compile, lint, build, audit, JSON/shell checks.

### Task 3: Release and Production migration
- [x] Update VERSION/changelog/release notes/bilingual README summary for v1.0.4.
- [ ] CI green on release branch, then verified Production app + PostgreSQL backup.
- [ ] Prepare `/opt/pvnetwork-panel` and `pvnetwork-panel.service`, start canary on a temporary local port, verify API/UI.
- [ ] Atomically switch nginx upstream to the new service, verify public/local health and Mirza, then retire the legacy service/path only after success.
- [ ] Merge/tag/release/artifact checksum verify; mark PVN-025 [x] only after final Production verification.
