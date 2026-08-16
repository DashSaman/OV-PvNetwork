# Changelog

## 1.0.0-rc1 — 2026-08-16

First public repository/bootstrap release of OV-PvNetwork.

### Distribution
- One-line bootstrap installer.
- Pinned upstream component manifest.
- `ovpv` lifecycle manager: install, update, backup, rollback, status, doctor and version.
- Safe production-source export workflow.
- CI syntax and secret-pattern checks.
- English and Persian documentation.

### Production-derived capabilities documented for stable snapshot
- Multi-node user assignment and reconciliation.
- Auto-node deployment foundation.
- Self-healing OpenVPN client profile generation.
- Real NIC metrics and realtime admin dashboard.
- Private Network subscription experience and client downloads.
- Monitoring, fleet and bandwidth-control integrations.
- AnyConnect/session-control integration hooks.
- Safe node lifecycle operations.
- Production health checks and recovery.

### Release note
`rc1` deliberately does not claim byte-for-byte parity with the running private production instance. `scripts/export-production.sh` exists to generate a sanitized source snapshot for that final stable parity release.
