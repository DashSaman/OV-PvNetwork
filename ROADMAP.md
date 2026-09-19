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

## Sequential patch queue

PVNetwork advances **one Production-visible task per patch release**. Exact execution status is recorded in `AGENTS.md`.

- **v1.0.6 — IN PROGRESS:** `PVN-027`, one consistent unique-user online truth across Dashboard and Users with a display-only direct-node fallback when central session hooks are missing/stale.
- The fallback does not synthesize enforcement sessions or alter device-limit semantics; raw per-node metrics remain separately visible.
- Following patches continue genuinely open `PVN-xxx` items; already-completed items are never repeated.
- Each release refreshes applicable Persian/English documentation, changelog/release notes, sanitized artifact and SHA256.

## Capability streams after current UX blockers

The permanent numbered backlog remains in `docs/FEATURE-BACKLOG.md` and covers: user lifecycle and scheduled renewal/reset; notifications; device/HWID/session control; QR and multi-format subscriptions; node/fleet/routing/capacity; Prometheus/Grafana/logging/reporting; enterprise identity/RBAC; webhooks/bots/jobs; WireGuard/Xray/Sing-box and optional proxy protocols; installer/update/backup/rollback; HA/DR; migrations and compatibility.

## Release rule

Released tags/assets are immutable. Every new Production-visible `PVN-xxx` task ships as the next sequential `1.0.x` GitHub Release after applicable tests, sanitization, verified backup, narrow deployment, health verification, bilingual documentation and release-asset verification pass.
