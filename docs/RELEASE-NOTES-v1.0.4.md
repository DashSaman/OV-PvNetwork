# PVNetwork Panel v1.0.4

Release date: 2026-09-19  
Task: `PVN-025` — Complete PVNetwork ownership namespace

## What changed

This patch makes the current product source and runtime naming consistently PVNetwork-owned. Installer defaults, lifecycle commands, systemd service names, application/config/state paths, backup formats, frontend storage identifiers and package metadata now use the canonical PVNetwork namespace.

Canonical names include:

- application root: `/opt/pvnetwork-panel`;
- systemd unit: `pvnetwork-panel.service`;
- system configuration: `/etc/pvnetwork`;
- host state: `/var/lib/pvnetwork-panel`;
- backups: `/var/backups/pvnetwork-panel` and `pvnetwork-backup-*`;
- lifecycle CLI: `pvnetwork`;
- frontend language key: `pvnetwork_language`.

A blocking CI ownership scan prevents forbidden legacy namespace variants from returning to the tracked source tree.
## Compatibility and safety

This release is a namespace/ownership patch. It does not intentionally change user quotas, node assignment semantics, certificate lifecycle, routing, firewall rules or tunnel configuration.

The Production deployment contract remains mandatory: read-only preflight, verified application and PostgreSQL backup, recorded rollback path, narrow deployment, minimal restart, local/public health verification and integration/log checks.

Production already uses the canonical application root and service name, so deployment must reconcile the verified release into that live runtime rather than repeat a destructive rename.

## Upgrade

Use the lifecycle manager after a verified backup:

```bash
pvnetwork doctor
pvnetwork backup
PVNETWORK_REF=v1.0.4 pvnetwork update
```

If any post-deploy health gate fails, restore the recorded pre-deploy application/runtime state and keep the task open.

## Known follow-up

`PVN-026` / v1.0.5 makes PostgreSQL the explicit Production database contract and moves the live database/role identity to `pvnetwork_panel`. Database identity migration is intentionally not bundled into this patch.
