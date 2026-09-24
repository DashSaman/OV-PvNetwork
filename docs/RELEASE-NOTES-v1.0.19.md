# PVNetwork Panel v1.0.19 — White-screen regression fix and hardening

`PVN-1003` repairs the live white-screen introduced by the v1.0.18 frontend deployment and hardens the release path so the failure class cannot recur.

## Incident
The v1.0.18 frontend bundle deployed to Production embedded the asset base path `/panel/` while the live panel path is different. The SPA shell (index.html) loaded, but its `<script>`/`<link>` URLs 404'd, leaving a blank page. Root cause: the deployment bundle was built locally with only `VITE_URLPATH` set, while Vite reads `URLPATH` (CI sets both); the build silently fell back to the default `panel`.

## Fixes
- Production was restored first: a correctly built bundle was deployed and the pre-incident hashed assets were restored alongside it so even browsers with a cached old index kept working.
- The release/build contract now states explicitly that `URLPATH` must be set to the deployed panel path for any production bundle.

The frontend bundle budget gate rises from 775000 to 820000 bytes: completing the 11 secondary language catalogs adds ~46 kB of translation strings to the main chunk (814.6 kB largest chunk). A follow-up task (`PVN-1004`) registers on-demand language loading to shrink the chunk again.

## Hardening
- The backend now serves the SPA `index.html` with `Cache-Control: no-cache`. Browsers may cache the shell but must always revalidate, so a future atomic asset/index switch can never strand clients on an old index referencing deleted hashed assets. Focused contract test added.

## Completed gaps
- All 11 secondary languages (ar, es, id, ja, pt_BR, ru, tr, uk, vi, zh_CN, zh_TW) now cover the full 407-key UI catalog; the 35 keys for Quick Edit, Add-User node selector, Router/MikroTik compatibility and username rename were translated.
- Production database and login role migrated from the legacy pre-rebrand identifier to `pvnetwork_panel`: backup-first with verified parity (31 tables, 71 users, 4 nodes, Alembic head `e7f8a9b0c1d2`), table ownership transferred to the application role, `.env` updated, and the previous database retained untouched as the rollback path. A short (~90 second) window of dashboard-live HTTP 500s occurred between the `.env` switch and the ownership grant; it was closed immediately and verified clean.

## Scope and safety
No OpenVPN, Node, Router compatibility listener, profile, certificate, routing or session behavior changes. Only `pvnetwork-panel.service` restarts are involved.

## Release gate
Exact-head CI, verified rollback backups, narrow deployment, local/public health verification, post-deploy log review, sanitized artifact plus SHA256 publish and public re-download verification.
