# Changelog

## 1.0.0 — 2026-09-19

First stable public baseline of OV-PvNetwork.

### User lifecycle
- Expired-user renewal without delete/recreate.
- Unlimited renewal with a fresh 30-day period.
- Finite renewal modes: preserve usage, reset usage or add traffic.
- Mirza renewal integration and regression tests.
- AnyConnect lifecycle kept on the same user identity.

### Operations
- Multi-node assignment, health and realtime traffic monitoring.
- Fleet maintenance, drain/resume and controlled upgrade/retry workflows.
- Bulk operations, transfer/rebalance and usage-history tooling.
- Emergency/canary bandwidth-policy controls.
- Verified manual backup and guarded restore workflow.

### Security and documentation
- Rate limiting, IP allowlist, TOTP 2FA and scoped API tokens.
- English and Persian README files.
- Sanitized screenshots for all major pages and core workflows.
- Full English/Persian visual UI guides.
- Public release source excludes production credentials, databases, profiles and private operational identifiers.
