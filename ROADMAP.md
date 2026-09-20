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

## Sequential patch queue

PVNetwork advances **one Production-visible task per patch release**. Exact execution status is recorded in `AGENTS.md`.

- **v1.0.12 next:** `PVN-032`, authenticated UI controls for panel path and main-admin username/password with hashed-password storage and atomic path rollback.
- Following patches continue genuinely open `PVN-xxx` items; already-completed items are never repeated.
- Each release refreshes applicable Persian/English documentation, changelog/release notes, sanitized artifact and SHA256.

## Capability streams after current UX blockers

The permanent numbered backlog remains in `docs/FEATURE-BACKLOG.md` and covers: user lifecycle and scheduled renewal/reset; notifications; device/HWID/session control; QR and multi-format subscriptions; node/fleet/routing/capacity; Prometheus/Grafana/logging/reporting; enterprise identity/RBAC; webhooks/bots/jobs; WireGuard/Xray/Sing-box and optional proxy protocols; installer/update/backup/rollback; HA/DR; migrations and compatibility.

## Release rule

Released tags/assets are immutable. Every new Production-visible `PVN-xxx` task ships as the next sequential `1.0.x` GitHub Release after applicable tests, sanitization, verified backup, narrow deployment, health verification, bilingual documentation and release-asset verification pass.
