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
- Responsive Subscription page hardening and bilingual browser proof.

### v1.0.3
- Inline user Quick Edit with assignment-aware synchronization and safe profile reuse/deactivation.

## Sequential patch queue

PVNetwork now advances **one Production-visible task per patch release**: `v1.0.2`, `v1.0.3`, `v1.0.4`, ... . Exact task status and the next release are always recorded in `AGENTS.md`.

- **v1.0.4 — IN PROGRESS:** PVN-025, complete PVNetwork ownership namespace.
- **v1.0.5 — QUEUED:** PVN-026, PostgreSQL-first Production contract and canonical database/role identity.
- Following patches continue the first genuinely open `PVN-xxx` item in `AGENTS.md`; already-completed items are never repeated.
- Each release refreshes the relevant Persian/English visual documentation, changelog/release notes, sanitized artifact and SHA256.

## Capability streams after current UX blockers

The permanent numbered backlog remains in `docs/FEATURE-BACKLOG.md` and covers: user lifecycle and scheduled renewal/reset; notifications; device/HWID/session control; QR and multi-format subscriptions; node/fleet/routing/capacity; Prometheus/Grafana/logging/reporting; enterprise identity/RBAC; webhooks/bots/jobs; WireGuard/Xray/Sing-box and optional proxy protocols; installer/update/backup/rollback; HA/DR; migrations and compatibility.

## Release rule

Released tags/assets are immutable. Every new Production-visible `PVN-xxx` task ships as the next sequential `1.0.x` GitHub Release after applicable tests, sanitization, verified backup, narrow deployment, health verification, bilingual documentation and release-asset verification pass.
