# PVN-1022 Smoke Revision Validation Plan

**Goal:** Restore the smoke gate for the existing alphanumeric migration chain while preserving rejection of missing, multiple and mismatched revisions.

**Architecture:** Keep the shell smoke stage and existing exit codes. Exercise its real Alembic stage in a temporary fixture; replace only the external Alembic CLI response. No runtime database writes or service restarts.

**Tech stack:** Bash, Python unittest, Alembic.

**Spec:** `AGENTS.md`, `docs/QA-RELEASE-GATE.md` and the owner-requested production audit.

## Constraints

- Candidate target: `v1.0.39`; stable task: `PVN-1022`. The independently discovered Axios security prerequisite (`PVN-1023`) reserves `v1.0.38`.
- Preserve all release, database and service safety gates.
- Never commit operational credentials, addresses or customer data.
- Keep the task open until release and authorized deployment evidence exist.

## Execution

- [x] Add executable regression tests for the shipped alphanumeric revision, ordinary hexadecimal revision, missing/multiple heads, missing current revision and mismatch.
- [x] Run the tests against unchanged code and capture the alphanumeric failure (four failures; hexadecimal and empty-head cases pass).
- [x] Expand revision filtering consistently for expected and current heads; preserve the one-head and equality checks (six tests pass).
- [ ] Run focused regression tests, shell syntax, compilation and the existing suite; report platform/dependency failures separately.
- [ ] Prepare the patch and deployment/rollback procedure. Verify app and native database backup before any authorized Production mutation.
- [ ] Keep release and Production status pending until all applicable gates pass.
