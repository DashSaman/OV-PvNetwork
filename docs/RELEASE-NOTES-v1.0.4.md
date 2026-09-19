# PVNetwork Panel v1.0.4

## Scope

`PVN-025` makes PVNetwork ownership explicit throughout the tracked project and runtime contract. The former upstream panel product identifier is not permitted anywhere in tracked paths or text; CI enforces that rule permanently.

## Changes

- Canonical application/runtime path: `/opt/pvnetwork-panel`.
- Canonical systemd unit: `pvnetwork-panel.service`.
- PVNetwork-owned configuration, push, monitoring, fleet, backup and restore paths/identifiers.
- Installer/update source resolves `DashSaman/OV-PvNetwork` releases.
- Python package, API version, frontend package and release metadata are aligned on `1.0.4`.
- Browser language persistence uses `pvnetwork_language` and can generically import a valid predecessor `*_language` value.
- SQLite fallback safely reuses a single existing database file instead of silently creating an empty database during a path/name migration.
- MIT copyright attribution for the original foundation is preserved without retaining the former product brand.

## Upgrade / Production safety

Production is live. Before switching runtime naming, take a verified application/runtime backup and a database-native PostgreSQL dump. Prepare and validate the new PVNetwork runtime in parallel on a temporary local port. Only after local API/UI checks pass should nginx be switched atomically. Verify public API/UI, changed workflow, logs, database readability and Mirza integration before retiring the previous runtime service/path.

Do not change firewall rules, default routes, tunnels, VPN nodes, certificates or unrelated services for this release. If any post-switch gate fails, restore the previous nginx target and runtime state immediately.
