# v1.0.38 — PVN-1023: Frontend dependency security refresh

Status: release candidate. This version has not been publicly released.

This patch follows v1.0.37. Changes are limited to the task described in the active `AGENTS.md` ledger. No database migration or VPN configuration change is required.

Validation includes the focused regression, the existing Linux CI gates and applicable frontend browser tests. Final exact-commit CI and Production deployment evidence are recorded in the private audit and the task ledger; a candidate status is not a completion claim.

Upgrade must preserve environment, database, certificates, subscriptions and existing VPN sessions. Use a verified source/build artifact and native database backup; do not use the legacy lifecycle updater for this rollout. Rollback restores the previous application/helper/index files from the recorded backup. Frontend assets are added before the index switches, and previous assets are retained.

Known overall hardening gaps: fresh-install public URL/TLS setup, installer/update integrity enforcement, lifecycle-native database backup/rollback integration and complete real-node bootstrap/traffic E2E remain open. These candidates do not make the entire project FINAL or RELEASE-READY.
