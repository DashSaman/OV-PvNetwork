# OV-PvNetwork v1.0.0

Stable public baseline for the production-derived OV-PvNetwork control plane.

## Highlights

- Multi-node OpenVPN user and node management.
- Expired-user renewal without recreation.
- Unlimited and finite-plan renewal modes.
- Optional AnyConnect user integration.
- Realtime dashboard and node health metrics.
- Fleet maintenance, drain/resume and controlled upgrade workflows.
- Bulk operations, transfer/rebalance and usage history.
- Emergency/canary bandwidth policies.
- TOTP 2FA, IP allowlist, rate limit and scoped API tokens.
- Verified backup download and guarded restore.
- English/Persian documentation with sanitized UI screenshots.

## Install

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/DashSaman/OV-PvNetwork/v1.0.0/install.sh)
```

Use on a fresh supported server. Existing production deployments should follow the backup/update path instead of running a fresh install blindly.
