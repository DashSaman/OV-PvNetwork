# PVNetwork Panel v1.0.0

First public stable baseline.

## Highlights

- Multi-node OpenVPN control plane with user/node lifecycle management.
- Automatic SSH node deployment from the admin UI.
- Per-user node assignment and global concurrent-session enforcement.
- Traffic quota, unlimited plans, expiry and renewal without delete/recreate.
- Unlimited Reset Usage starts a new 30-day period from the reset date while preserving the same account identity.
- Self-healing OpenVPN profile validation/rebuild on download.
- Optional per-user AnyConnect integration.
- Node CPU/RAM/uptime/network metrics, health controls, drain/maintenance and fleet foundations.
- Reseller quotas/credit ledger, bulk operations, rebalance and emergency bandwidth controls.
- Audit, scoped API tokens, rate limiting, IP allow-list and TOTP/2FA foundations.
- Backup/restore, monitoring hooks, usage history and domain activity.
- Branded multilingual subscription page, client downloads, smart server recommendation and Web Push renewal reminders.
- Mirza integration endpoints.
- Public-safe bilingual and illustrated documentation.

## Public-source privacy

The release archive is sanitized before publication. Production `.env` files, credentials, infrastructure hostnames/IPs, customer data, databases, logs, backups, VPN profiles, private keys and certificates are excluded. Example values use documentation domains/address ranges.

## Compatibility

- Ubuntu 22.04 LTS
- Ubuntu 24.04 LTS
- Debian 12
- Initial third-party foundation snapshot: historical v1.7.10 lineage
- Upstream OV-Node base: v1.3.6

## Installation

Use the one-command installer from the repository README on a fresh server. Existing live installations are not overwritten by the fresh installer.

## Release discipline

The `v1.0.0` tag and assets are immutable. Compatible fixes ship as `1.0.x`; new backward-compatible capabilities as `1.x.0`; breaking changes as `2.0.0`.
