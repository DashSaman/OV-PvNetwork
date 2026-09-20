# PVN-032 / v1.0.12 — Main Admin & Panel Path Runtime Settings Design

## Goal
Allow the authenticated `main_admin` to change the panel URL path, main-admin username, and main-admin password from the web UI without interrupting OpenVPN, Nodes, or VPN users.

## Agreed UX and safety contract
- Controls live inside the existing **Security Settings** page; no new top-level navigation item is required.
- Every change requires re-entering the current main-admin password.
- Passwords are never stored or logged in plaintext; only the existing strong password hash format is persisted.
- A path change keeps the previous path alive as a **307 temporary redirect for 5 minutes**, preserving the requested suffix, then the old path becomes a normal 404.
- The currently active browser session survives a username/password/path change and is moved to the new path automatically.
- Other previously issued main-admin browser JWTs are invalidated when main-admin credentials change.
- OpenVPN services, Node services, Router compatibility listeners, and user tunnels are never restarted by this feature.

## Current constraints
The current application reads `ADMIN_USERNAME`, `ADMIN_PASSWORD_HASH`, and `URLPATH` from `.env` at process startup. Frontend asset URLs and React Router basename are also built using `URLPATH`, and FastAPI mounts the SPA path statically during import. Therefore a path change requires a validated frontend rebuild and a controlled panel-process restart.

## Architecture
Introduce a small `panel_runtime_settings` backend module plus a detached apply helper. The API performs authentication, validation, staging and returns a signed apply ticket. The helper performs the atomic switch and rollback independently of the Uvicorn process that is being restarted.

The source of truth remains `.env` for `ADMIN_USERNAME`, `ADMIN_PASSWORD_HASH`, `URLPATH`, and `VITE_URLPATH`. No plaintext password column is added to PostgreSQL. A tiny runtime state file stores only non-secret transition metadata: old path, new path, redirect expiry, change id, and status.
## Backend API
Add main-admin-only endpoints under `/api/security/panel-settings`:
- `GET /api/security/panel-settings` returns current username, current panel path, redirect status, and whether a change job is active. It never returns a password hash.
- `POST /api/security/panel-settings/apply` accepts `current_password`, optional `new_username`, optional `new_password`, and optional `new_path`.
- `GET /api/security/panel-settings/jobs/{change_id}` accepts a short-lived, change-scoped status token and returns only non-secret progress/result data, so polling survives the controlled restart without depending on the old or new admin JWT.
- Only interactive `main_admin` JWT authentication is accepted for mutation; API tokens and delegated admins are rejected.
- The endpoint verifies `current_password` against the current main-admin hash before any staging work.
- If nothing actually changes, return a validation error rather than restarting the panel.

## Validation
- Username: 3–64 characters, trimmed, no control characters, and must not collide with an existing delegated-admin username.
- New password: minimum 12 characters and must differ from the current password. Hash with the existing `backend.auth.hash.hash_password` helper.
- Path: 3–64 characters and only `[A-Za-z0-9_-]`; no slash, dot, whitespace, percent encoding, or control characters.
- Reserved path names are rejected, including `api`, `healthz`, `doc`, `redoc`, `openapi.json`, `assets`, subscription paths, and other server-owned top-level routes.
- Path comparison is case-insensitive for collision checks.

## Credential session semantics
Main-admin JWT validation will additionally require `sub == config.ADMIN_USERNAME`. This closes the current gap where an old `main_admin` JWT remains valid even after the configured username changes.

When credentials change, the apply response includes a pending replacement JWT minted for the candidate username/generation plus a short-lived change-scoped status token. The frontend keeps the replacement JWT only in `sessionStorage` until the job reaches `complete`; then it promotes it to the normal auth store. On rollback it discards the pending JWT and keeps the original session. Existing old main-admin JWTs fail after a successful restart because their subject and/or generation no longer matches the configured values. If only the password changes and username does not, the generation still rotates.

If the main-admin username changes, the helper migrates the matching `PrincipalSecurity` row in the same rollback-aware switch so existing TOTP configuration and encrypted secret remain attached to the main administrator. Historical `ApiToken.created_by` values are not rewritten; API tokens keep their independent revoke/expiry semantics.
The generation is stored as a non-secret `MAIN_ADMIN_AUTH_GENERATION` value in `.env`. Main-admin JWTs carry `gen`; validation requires it to equal the configured generation. A credential change generates a new random generation. Path-only changes keep the generation unchanged.

## Atomic apply workflow
1. Acquire an exclusive settings-change lock so two administrators cannot mutate runtime settings concurrently.
2. Re-verify the current password and re-read the current `.env` immediately before staging.
3. Create a rollback directory containing `.env`, `frontend/dist`, relevant Nginx config, runtime transition state, service metadata, and checksums.
4. Produce a candidate `.env` in the rollback/staging area; never overwrite the live file yet.
5. Build the frontend into a staging directory with candidate `URLPATH`/`VITE_URLPATH`.
6. Start a candidate panel instance on `127.0.0.1:19002` with the candidate environment and staged frontend.
7. Verify candidate `/healthz`, candidate panel HTML, referenced asset HTTP 200, candidate credential hash/username loading, reserved-route isolation, and authenticated API wiring without weakening or bypassing existing TOTP state.
8. If any preflight fails, stop the candidate, delete temporary state, leave Production unchanged, and report the failure.
9. If preflight passes, atomically replace `.env` and `frontend/dist`, preserving mode/ownership and fsyncing the parent directory.
10. Write redirect transition metadata before restarting canonical `pvnetwork-panel.service`.
11. Restart only `pvnetwork-panel.service`; do not restart OpenVPN, Node, Router OpenVPN, Nginx, or tunnel services.
12. The detached helper polls canonical `127.0.0.1:19001/healthz`, the new panel path and one built asset.
13. On success, mark the job complete and stop the candidate. On failure or timeout, restore `.env` and `frontend/dist`, restart the panel once, verify the previous path, and mark the job rolled back.

The helper must have a finite timeout and an idempotent change id so an interrupted browser request cannot trigger the same mutation twice.
## Old-path redirect
Add an early middleware that reads the non-secret transition state. While `now < redirect_expires_at`, requests whose first path segment equals the previous panel path receive HTTP 307 to the same suffix under the new path. Example: `/old/users` becomes `/new/users`, and `/old/assets/app.js` becomes `/new/assets/app.js`.

The redirect applies only to the previous panel prefix, never `/api`, subscription routes, health endpoints, or arbitrary paths. After five minutes the middleware stops redirecting; because the previous SPA route is no longer mounted, the old path naturally returns 404. Expired transition files may be cleaned lazily on the next settings read or application startup.

## Frontend behavior
Extend `SecuritySettings.jsx` with a main-admin-only **Panel & Main Admin** card showing current path and username plus password fields that are never pre-filled.

Before submission, the UI displays a confirmation summary. During apply it shows the stages returned by the job-status endpoint: validating, building, canary, switching, verifying, complete, or rolled back.

If the response contains a replacement JWT, keep it only as pending state in `sessionStorage`; poll job status with the separate change-scoped status token. Promote the replacement JWT only after `complete`. For a path change, then navigate the browser to `/${new_path}/security`. If the canonical panel is briefly restarting, retry health/status with bounded backoff instead of showing a blank page. A rollback discards the pending token, sends the browser back to the previous path, and surfaces the rollback reason.

## Error handling and audit
- Never include plaintext current/new passwords, password hashes, JWTs, or `.env` contents in logs, audit payloads, API errors, or job state.
- Audit records include actor, change id, which fields changed, old/new path or username where applicable, result, and rollback reason.
- A failed build/canary is a no-op on Production.
- A failed canonical verification triggers automatic rollback.
- A rollback failure is a critical audit event and must leave enough backup metadata for manual restoration without touching VPN services.
## Tests
Backend unit/integration tests must cover:
- only interactive `main_admin` can mutate settings;
- current-password re-authentication is mandatory;
- username/password/path validation and reserved-path rejection;
- plaintext password absence from files/logs/job payloads;
- pending replacement JWT validity, change-scoped status-token authorization, and invalidation of previous main-admin JWTs after successful credential rotation;
- username change preserving the main-admin `PrincipalSecurity`/TOTP record and rollback restoring its previous username;
- path-only change preserving auth generation;
- exact 5-minute old-path redirect behavior and suffix preservation;
- expired old path returning 404;
- candidate build/canary failure leaving Production unchanged;
- post-switch verification failure restoring the exact previous `.env` and `frontend/dist`;
- idempotent change ids and concurrent-change lock behavior.

Frontend tests must cover form validation, confirmation, replacement-token storage, progress states, path navigation, bounded restart retry, rollback messaging, desktop/mobile layout, and no blank page after a successful path change.

Production canary/release verification must capture before/after PIDs and config hashes proving normal OpenVPN and Node services were not restarted. Public `/healthz`, login, new path, assets and authenticated Security Settings must pass. The previous path must redirect during the grace period and be verified as 404 after expiry.

## Files/components expected to change
- `backend/auth/auth.py` for main-admin JWT subject/generation enforcement and replacement-token support.
- `backend/config.py` for `MAIN_ADMIN_AUTH_GENERATION`.
- a focused backend runtime-settings service/helper and API router under existing security/settings ownership.
- `backend/app.py` or a dedicated middleware module for bounded old-path redirects.
- `frontend/src/pages/SecuritySettings.jsx` and translation resources.
- installer/update/env migration helpers so existing installations receive a generation value without losing credentials.
- tests, bilingual release notes, changelog, roadmap/agent ledger, sanitized release artifact and checksum.
## Non-goals
- This release does not rename upstream `ov-node` repository/path/service identities.
- It does not change OpenVPN authentication policy, certificates, Router listener behavior, device limits, subscriptions, routing, or Node configuration.
- It does not add multi-main-admin accounts; delegated admins remain managed by the existing Admin Management flow.
- It does not expose arbitrary `.env` editing through the UI.

## Release acceptance criteria
`v1.0.12 / PVN-032` is complete only when all automated CI/security/browser tests pass, a verified rollback backup exists, candidate canary validation passes, Production is switched successfully, the current admin remains usable at the new path, old browser JWTs are invalidated after credential rotation, the old path redirects for five minutes and then returns 404, and OpenVPN/Node PID plus normal OpenVPN config hash prove no VPN-service interruption.

The final GitHub Release must contain the sanitized source artifact and SHA256 checksum, and the downloaded artifact must be re-verified after publishing.