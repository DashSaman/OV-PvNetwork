# PVNetwork Panel v1.0.0 Worklog

## 2026-09-18
- Created `release/v1.0.0-baseline` branch.
- Added release baseline design and implementation plan.
- Added renewal planning core with regression tests.
- Added admin renewal API route and Mirza renewal API route in production source.
- Added renewal modal and UI wiring in production source.
- Verified 8 renewal/UI smoke tests pass.
- Verified backend Python compile passes.
- Verified Vite production build passes.
- Restarted production panel and verified both renewal routes exist in OpenAPI.
- Production backup taken before renewal source changes.

## Release blockers still open
- Sync all changed production files to this branch.
- Add bilingual README/docs and sanitized screenshots.
- Add installer/update/backup/rollback tooling and dry-run verification.
- Complete competitive feature matrix and issue backlog.
- Run full release verification and package/tag v1.0.0.
