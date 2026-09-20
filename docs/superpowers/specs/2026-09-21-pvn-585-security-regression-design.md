# PVN-585 / v1.0.14 — Security Regression Design

## Purpose

Ship a bounded security-regression release after v1.0.13 without introducing a new identity architecture. The release must turn the current security posture into executable regression coverage, verify high-risk trust boundaries, and fix only vulnerabilities that are actually reproduced.

## Release boundary

This release covers authentication, authorization, API-token scope enforcement, IDOR resistance, CORS/CSRF posture, XSS, SQL injection, rate limiting, proxy/IP trust, security headers, secret exposure, sensitive file permissions, and public/private route exposure.

It does **not** add SSO, passkeys, LDAP/RADIUS, new RBAC models, new roles, new session products, or unrelated UX work. Findings that require an architectural identity redesign are documented and deferred to a later release rather than expanded into v1.0.14.

## Safety model

All state-changing adversarial tests run against an isolated test database or validated canary. Production receives only non-destructive probes such as authentication failures, authorization checks, header checks, route exposure checks, and read-only health verification.

No test may delete or mutate real users, nodes, credentials, subscriptions, firewall rules, OpenVPN configuration, Router listener configuration, or live sessions. OpenVPN and Node services are isolation invariants for rollout.

## Threat boundaries

The primary trust boundaries are browser → Nginx → FastAPI, administrator JWT → protected API, scoped API token → API middleware → protected API, Nginx → client-IP derivation, panel → Node APIs, and public integration routes → database operations.
## Required regression suite

The suite must cover these behaviors:

1. JWT tampering, wrong signature, wrong subject/type, expired token, and stale main-admin generation are rejected.
2. Disabled delegated admins cannot authenticate or continue using previously valid admin JWTs.
3. API tokens are accepted only through their supported prefixes, expiry/revocation is enforced, and read/write scopes cannot cross users/nodes/settings/audit boundaries.
4. Main-admin-only operations remain inaccessible to delegated admins and API tokens, including panel credential/path changes and security administration.
5. Object identifiers cannot be changed to access another principal's protected object or bypass ownership/role checks where object-level authorization exists.
6. Login and general API throttles resist spoofed leading X-Forwarded-For values when requests arrive through the trusted loopback reverse proxy.
7. Security Settings allowlist lockout validation uses the same canonical client-IP derivation as middleware.
8. CORS allows only configured origins and does not accidentally grant credentialed cross-origin access to arbitrary origins.
9. The bearer-token architecture is explicitly verified as not relying on ambient cookies; CSRF controls are evaluated against actual credential transport rather than added mechanically.
10. User-controlled strings are tested for reflected/stored HTML/script execution in applicable browser/API paths.
11. SQL inputs are exercised with injection payloads against parameterized query paths, including public integration endpoints, without mutating Production data.
12. Production security headers, disabled docs/OpenAPI exposure, secret-file modes, API output redaction, and sanitized release material remain enforced.

## Known candidate finding

`backend/security_middleware.py::_client_ip()` trusts the final X-Forwarded-For element when the immediate peer is loopback, matching the Nginx append model. `backend/routers/security.py` currently performs allowlist self-lockout validation using the first X-Forwarded-For element. v1.0.14 must first reproduce this inconsistency with a failing test. If reproduced, the endpoint must reuse the canonical client-IP helper rather than maintain a second parser.
## Finding policy

Every suspected vulnerability follows reproduce → minimize → fix → regression-test. A finding is not counted from static suspicion alone. The failing test or controlled probe must demonstrate the security impact before implementation changes are made.

Low-risk fixes that preserve existing interfaces may ship in v1.0.14. A finding that requires a new authentication model, database ownership redesign, or broad RBAC migration is recorded with evidence and deferred to a dedicated release.

No security test is weakened merely to make CI green. If existing behavior is intentionally accepted, the rationale and threat assumptions must be documented explicitly.

## Expected code shape

Prefer shared security primitives over duplicate parsing or authorization logic. In particular, client-IP derivation should have one reusable implementation consumed by middleware and security-setting validation.

New regression tests should be grouped by security boundary rather than one monolithic pentest script. Tests must be deterministic and safe to run in CI without external Production dependencies.

A small read-only Production verification script may be added if needed, but it must not contain credentials, destructive payloads, infrastructure secrets, or customer data.

## CI gates

The existing dependency audit, Bandit gate, unit/governance suite, Router OpenVPN safety/real dual-auth checks, frontend production build/runtime audit, browser responsive matrix, secret/private-material guard, and installer lifecycle checks remain mandatory.

v1.0.14 adds focused security-regression tests and must preserve full CI success. Any new scanner must be deterministic enough for release gating and must not upload source, secrets, or private artifacts to third-party services.
## Production verification and rollout

Before mutation, capture a verified rollback point including source, `.env`, PostgreSQL dump/restore test, Nginx configuration, and current panel/Node/OpenVPN PIDs plus OpenVPN config hashes.

Deploy through the established canary flow: exact merged-main candidate on 19002, validate health/UI/API, temporarily switch public traffic to canary, update canonical 19001, restore Nginx to 19001, and run `pvnetwork-canary-retire-guard` before terminating canary. The guard must report `CANARY_RETIRE_SAFE=YES` and both canonical/public health must be 200.

Only `pvnetwork-panel.service` may restart when required by the patch. Node and normal OpenVPN services must not be restarted by the rollout, and their baseline identity/config evidence must be rechecked afterward.

Production security probes are read-only/non-destructive and include public health/UI, unauthenticated protected-route rejection, docs/OpenAPI exposure, security headers, CORS behavior, rate-limit sanity, Nginx upstream, and final panel smoke.

## Release completion

The final main commit must pass full CI after Production evidence is recorded. Tag `v1.0.14` must resolve exactly to that commit. Publish a sanitized source artifact plus SHA256, re-download both from GitHub, verify checksum, `VERSION=1.0.14`, archive inventory, and absence of forbidden private material.

Bilingual release notes and the project ledger/roadmap must identify reproduced findings, fixes, deferred architectural findings, test evidence, Production isolation evidence, and the final artifact hash.

## Acceptance criteria

- Security regression coverage exists for every category listed above.
- The X-Forwarded-For/allowlist inconsistency is either reproduced and fixed with a shared parser, or disproved with an explicit regression test.
- No confirmed Critical/High finding within the approved v1.0.14 scope remains unfixed at release time.
- Deferred architectural findings have evidence and a named follow-up backlog item.
- Full CI, rollback verification, canary, Production smoke, release publication, and public re-download verification all pass.
