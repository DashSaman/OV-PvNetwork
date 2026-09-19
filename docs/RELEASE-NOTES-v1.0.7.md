# PVNetwork Panel v1.0.7 — Online Presence Synchronization Hotfix

**Patch task:** `PVN-031`

Dashboard and User Management already shared the v1.0.6 online-user merge algorithm, but independent polling could still land on adjacent live snapshots. v1.0.7 adds one short-lived process-wide snapshot and a lightweight role-scoped User Management presence endpoint.

## Safety
- Display-only; no synthetic `active_sessions` writes.
- Device-limit acquire/heartbeat/release enforcement is unchanged.
- No database schema migration.
- No OpenVPN profile, certificate, route, firewall or tunnel changes.
