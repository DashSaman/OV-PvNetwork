# PVNetwork Panel v1.0.14 — Security Regression

`PVN-585` turns the panel's current security boundaries into repeatable release gates. This is a hardening and regression release, not a new identity/RBAC architecture.

## Reproduced and fixed findings

- **Proxy/IP consistency:** Security Settings used the first `X-Forwarded-For` value for allowlist self-lockout validation while middleware used the trusted final value appended by loopback Nginx. Both now use one canonical client-IP helper.
- **API-token privilege boundary:** Security administration previously treated an API-token principal with `type=main_admin` as an interactive main administrator. Security, panel-runtime settings and backup administration now share one interactive-main-admin guard that rejects API-token authentication.
- **API-token prefix validation:** JWT fallback could accept a database token with an unrelated prefix if its hash existed. Only the supported `pvn_` and legacy `ovp_` prefixes now enter API-token lookup.
- **Scope path classification:** Scope middleware used substring matching, so look-alike settings paths containing `/users` or `/nodes` could be classified into the wrong scope area. Classification now uses exact API resource prefixes, including nested Operations, AnyConnect, and Router/OpenVPN user/node routes.

## Controls verified as already safe

JWT signature/expiry, main-admin subject/generation, disabled delegated-admin sessions, backup identifier traversal, ownership checks, panel change-token replay protection, SQL parameterization, protected-route inventory, output redaction, CORS exact-origin behavior, bearer-only browser auth posture, React XSS escaping and sensitive-file modes all passed focused regression coverage.

## New permanent release gates

- Dedicated Python security-regression suite in GitHub Actions.
- Mock-only Chromium XSS regression in the existing browser matrix.
- Credential-free, GET-only Production probe for health, security headers, disabled docs/OpenAPI, unauthenticated protected routes and untrusted-origin CORS behavior.
- Static guard against direct f-string/format interpolation into SQLAlchemy `text()` runtime SQL.

## Deferred architecture

No new Critical/High architectural finding was reproduced. Broader session-management and cookie/session hardening remain planned under `PVN-508` and `PVN-528`; they are roadmap improvements, not findings claimed by this release.

## Production safety boundary

Adversarial state-changing tests run only against isolated test state/canary. Production verification is read-only and credential-free. The v1.0.14 deployment path does not target Node or normal OpenVPN configuration/service; it uses verified backup/restore evidence, validates candidate `19002`, returns Nginx to canonical `19001`, and requires `CANARY_RETIRE_SAFE=YES` before retiring canary.

## Production evidence

- The pre-change backup passed checksum and PostgreSQL restore validation. The exact-main canary on `19002` served v1.0.14 successfully before canonical `19001` was upgraded.
- The installed retirement guard returned `CANARY_RETIRE_SAFE=YES`; after canary termination, health, panel root and Users all remained HTTP 200 with no new 502 observed.
- The credential-free security probe and full Production smoke passed; the reserved synthetic login-rate-limit check reached HTTP 429 at configured limit 10 with `Retry-After: 60`.
- The Node process remained unchanged and both normal/Router OpenVPN configuration hashes remained unchanged. During the same window, the pre-existing periodic lifecycle independently auto-disabled an eligible user and its legacy Node status-change path restarted normal OpenVPN. Evidence attributes that restart to the existing lifecycle, not the v1.0.14 deployment; removing whole-service restarts is deferred to `PVN-376` / `PVN-398`.

The immutable release is complete only after final main CI, exact tag resolution, sanitized artifact publication, SHA256 publication and public re-download verification.
