# PVNetwork Panel Roadmap

> Production is live and under load. `AGENTS.md` is the execution source of truth. This public roadmap is a sanitized summary only.

## Released

### v1.0.0
- Sanitized stable public baseline.
- User renewal without delete/recreate, unlimited 30-day reset behavior, Mirza renewal endpoint.
- Bilingual illustrated documentation, release artifact and SHA256.

### v1.0.1
- Main-admin responsive/mobile hardening across current primary routes and key dialogs.
- Telegram Node DOWN/UP transition alerts with deduplication and a Monitoring Settings toggle.
- Sanitized Persian/English desktop/mobile screenshots and regression gates.

### v1.0.2
- Responsive Subscription page (`PVN-111`) with bilingual mobile/desktop regression coverage.

### v1.0.3
- Inline user Quick Edit and safe multi-node assignment behavior (`PVN-205`).

### v1.0.4
- Complete PVNetwork-owned source/runtime namespace and release-engineering guard (`PVN-025`).

### v1.0.5
- Add User node selector with explicit assignment authority and no silent new-node widening (`PVN-026`).

### v1.0.6
- Shared unique online-user truth across Dashboard and Users with a display-only direct-node fallback (`PVN-027`).

### v1.0.7
- Online-presence snapshot synchronization hotfix so adjacent views do not race between samples (`PVN-031`).

### v1.0.8
- Production security hardening: hashed main-admin credentials, pinned SSH host keys, dependency/static audits, response/login hardening and reversible host filtering (`PVN-028`).

### v1.0.9
- Opt-in Router/MikroTik OpenVPN compatibility on an isolated listener/profile with certificate + password dual authentication and no change to normal certificate-only users (`PVN-029`).

### v1.0.10
- Backward-compatible migration of PVNetwork-owned token/header/helper aliases while retaining legacy reads and leaving upstream `ov-node` identities plus normal OpenVPN untouched (`PVN-030`).

### v1.0.11
- Live online-user truth correction: zero-client Node samples clear stale display state and orphan Common Names no longer inflate managed-user counts (`PVN-033`).

## Released

### v1.0.12
- Authenticated runtime main-admin username/password and panel-path controls with re-authentication, generation-bound JWT rotation, five-minute old-path redirect, candidate canary and automatic rollback (`PVN-032`).
- Production verification is green: rollback backup, canary, public/local UI and authenticated API checks passed; normal OpenVPN PID/config hashes remained unchanged; Node healthcheck and smoke rollout guards were corrected and passed both explicit and timer-driven verification.
- The live Production path was intentionally left unchanged because no new owner-selected target path was supplied. Tag/assets were published and the public artifact was re-downloaded with SHA256 verification PASS.


## Production verified — publication gate

### v1.0.13 — RELEASED
- Fail-closed Production canary-retirement procedure: canonical Nginx upstream, syntax check, successful Nginx reload, local health and public health must all pass before canary shutdown (`PVN-894`).
- Direct regression guard for the brief v1.0.12 HTTP 502 caused by stopping the validated canary before Nginx had been cut back to canonical. Production rollout and post-canary public verification passed; immutable tag/assets and post-download SHA256 verification remain.

## Owner-approved priority track (2026-09-24)

The owner approved the following five-release track plus a protocol bridge. Each item keeps the full test → CI → release → safe-deploy cycle and must never disturb unrelated services on the production host.

1. **v1.0.23 — `PVN-211` Smart subscription page: QR codes + per-device guides.** QR for the subscription page and per-server config downloads, plus device-specific quick-connect steps (Windows/macOS/iOS/Android/Linux/Router). Highest impact per effort; builds on the existing subscription page.
2. **`PVN-204` Self-service user portal.** Users see traffic/expiry/devices and request renewal; resellers get notified. Removes most support tickets.
3. **`PVN-607..609` Telegram management bot.** Admin and reseller levels (quick user ops, quota reports) on top of the existing one-way monitor.
4. **`PVN-214/216` + `PVN-221/222` Import/export and user groups.** Marzban/CSV migration path and plan-level policies for scale.
5. **`PVN-202/203` + `PVN-428/430` Renewal-aware notifications.** Multi-stage expiry/traffic alerts through Telegram plus optional email/webhook.
6. **Bridge to v2.0 — `PVN-700` WireGuard.** Single clean protocol alongside OpenVPN before any Xray/Reality work (deferred to the v2.0 line per issue #12).

Explicit non-goals (recorded to protect focus): SSO/SAML/LDAP, public status page, control-plane HA and new admin dashboards — none of them advance the sales/user experience where the competitors are actually ahead.

## Sequential patch queue

PVNetwork advances **one Production-visible task per patch release**. Exact execution status is recorded in `AGENTS.md`.

- **v1.0.13 released:** `PVN-894` fail-closed canary retirement; immutable artifact/re-download verification complete.
- **v1.0.14 released:** `PVN-585` security regression — four reproduced boundary defects fixed; permanent Python/browser/read-only Production gates added; immutable artifact and public SHA verification complete.
- **v1.0.15 Production-verified:** `PVN-376` / `PVN-398` per-user OpenVPN lifecycle preservation — Enable/Disable/Delete no longer restart the whole normal OpenVPN service; existing legacy Nodes receive a self-contained lifecycle patch and Production synthetic verification preserved the OpenVPN PID/config hash.
- **v1.0.16 released:** `PVN-022` safe multi-node username rename — durable staging/cutover/rollback, immediate old-profile revocation with no grace period, UUID/accounting/assignment preservation, and no whole-service OpenVPN restart. Tag/artifact published; Production deployment completed with the v1.0.17 rollout (see ledger).
- **v1.0.17 released:** `PVN-1000` debounced CPU threshold alerts — two consecutive at-threshold samples to fire, two consecutive recovered samples with a strict 5-point margin to clear, persisted threshold counters across monitor restarts, and stale offline-node counters dropped. Closes the live-Production CPU alert flapping observed while other services were under load. No OpenVPN/Node/Router/session behavior changes.
- **v1.0.18 released:** `PVN-1002` panel release-version badge — the Dashboard header shows the running release next to LIVE · REALTIME, read at runtime from public `/healthz`; display-only, deployed as an atomic frontend switch with no backend restart.
- **v1.0.19 released:** `PVN-1003` white-screen regression fix — correct asset base path for production bundles (`URLPATH`), `Cache-Control: no-cache` on the SPA index, full 407-key coverage in all 11 secondary languages, and the Production database/login role rebranded to `pvnetwork_panel` backup-first with the legacy database retained as rollback.
- **v1.0.20 released:** `PVN-1005` uniform language switching — all 463 used translation keys resolve in every one of the 13 shipped languages, Router/MikroTik modal direction follows the active language, and a permanent catalog-parity CI gate blocks future mixed-language regressions.
- **v1.0.21 released:** `PVN-1006` + `PVN-1007` (owner-directed combined patch) — full language uniformity (28 Persian-valued keys replaced across non-Persian catalogs, ~100 hardcoded Persian strings in Backup/AnyConnect/reseller UIs moved into the translation system, permanent value-purity CI gates) and Router/MikroTik one-time username/password credentials generated at user creation.
- **v1.0.22 released:** `PVN-1008` reliable automatic node deployment — the node-side allowlist source auto-detects from the SSH session (optional field), firewall rule insertion survives empty INPUT chains, IPv6 panels get a proper allow branch, and post-install verification failures are actionable.
- **v1.0.23 released:** `PVN-211` smart subscription page — page-level and per-server QR codes rendered client-side by a vendored MIT library (same-origin, CSP-safe) plus per-device quick-connect guides (Windows/macOS/iOS/Android/Linux/MikroTik) in fa/en.
- Following patches continue genuinely open `PVN-xxx` items; already-completed items are never repeated.
- Each release refreshes applicable Persian/English documentation, changelog/release notes, sanitized artifact and SHA256.

## Capability streams after current UX blockers

The permanent numbered backlog remains in `docs/FEATURE-BACKLOG.md` and covers: user lifecycle and scheduled renewal/reset; notifications; device/HWID/session control; QR and multi-format subscriptions; node/fleet/routing/capacity; Prometheus/Grafana/logging/reporting; enterprise identity/RBAC; webhooks/bots/jobs; WireGuard/Xray/Sing-box and optional proxy protocols; installer/update/backup/rollback; HA/DR; migrations and compatibility.

## Release rule

Released tags/assets are immutable. Every new Production-visible `PVN-xxx` task ships as the next sequential `1.0.x` GitHub Release after applicable tests, sanitization, verified backup, narrow deployment, health verification, bilingual documentation and release-asset verification pass.
