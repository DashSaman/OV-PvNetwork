# v1.0.41 candidate — PVN-1025

Verified fresh installer, private pinned toolchain, atomic release staging, truthful secure Setup Mode and generic public smoke path defaults. Fresh SQLite uses current constrained metadata through an isolated atomic initializer; PostgreSQL keeps its migration chain. Existing installations/data are refused by the fresh path. [Installer/recovery details](INSTALLER-CANDIDATE.md).

Local checkpoints: 405 Linux tests and three real x86_64 distribution/systemd installation snapshots passed; final exact-commit integration/CI is required after final code changes. Public HTTPS is gated in code and requires real certificate/proxy verification. Public ACME/ARM64/external VPN tests are not claimed.

No additional Production deployment occurred. Current Production is the previously verified 1.0.40 candidate. Stable publication remains blocked by remaining lifecycle/node/privacy and final release gates. Do not use the legacy updater; existing-host adoption and rollback are separate operations. Previous published tags/assets remain immutable.
