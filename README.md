<div align="center">

# OV-PvNetwork

**Production-oriented multi-node OpenVPN control plane with optional AnyConnect integration**

[![Version](https://img.shields.io/badge/version-1.0.0-brightgreen?style=flat-square)](./VERSION)
[![Ubuntu](https://img.shields.io/badge/Ubuntu-22.04%20%7C%2024.04-E95420?style=flat-square&logo=ubuntu&logoColor=white)](#requirements)
[![License](https://img.shields.io/badge/license-MIT-green?style=flat-square)](./LICENSE)
[![Upstream](https://img.shields.io/badge/upstream-OV--Panel-blue?style=flat-square)](https://github.com/primeZdev/ov-panel)

**English** · [فارسی](./README.fa.md)

</div>

OV-PvNetwork is a production-derived distribution and operations layer built on the open-source OV-Panel / OV-Node ecosystem. It keeps the simple OpenVPN user workflow while adding multi-node operations, renewal, AnyConnect integration, monitoring, security controls, backup/restore, health scoring, traffic controls and safer deployment tooling.

> Public screenshots and examples are sanitized. They intentionally hide user rows, credentials, addresses, API keys, traffic values and private production identifiers.

## Visual tour

### Dashboard, users and nodes

![Dashboard, users and nodes](./docs/images/ui/01-control-plane.jpg)
### Administration, operations and security

![Administration, operations and security](./docs/images/ui/02-admin-security.jpg)

### Advanced fleet, monitoring and bandwidth controls

![Advanced fleet, monitoring and bandwidth controls](./docs/images/ui/03-operations.jpg)

Every major page and the most important workflows are documented with individual screenshots in:

- [Complete English UI guide](./docs/UI-GUIDE.md)
- [راهنمای کامل فارسی رابط کاربری](./docs/UI-GUIDE.fa.md)

## Core capabilities

| Area | Included in v1.0.0 |
|---|---|
| Users | Create, edit, activate/deactivate, delete, renewal, usage reset, profile/subscription delivery |
| Renewal | Expired-user renewal, unlimited renewal, finite preserve/reset/add-traffic modes |
| AnyConnect | Per-user enable/disable, password generation/change, shared user identity |
| Multi-node | Node CRUD, health view, user assignment, safe node lifecycle |
| Fleet | Health score, maintenance, drain/resume, controlled upgrade/retry workflows |
| Monitoring | Realtime traffic dashboard, node CPU/RAM/uptime, Telegram monitoring configuration |
| Security | IP allowlist, rate limiting, TOTP 2FA, scoped/expiring API tokens |
| Operations | Bulk user actions, transfer/rebalance tools, usage history, audit/operational views |
| Bandwidth | Emergency off, policy preview/canary/activate, groups and per-node status |
| Backup | Verified manual backup download and guarded restore workflow |
| Integrations | Mirza integration API, OpenVPN node API, optional AnyConnect/ocserv hooks |
## Quick installation

Run on a **fresh** supported server as `root`:

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/DashSaman/OV-PvNetwork/v1.0.0/install.sh)
```

The installer uses the tagged `v1.0.0` source instead of following an unpinned development branch.

After installation, use the lifecycle manager:

```bash
ovpv status
ovpv doctor
ovpv version
ovpv backup
ovpv update
ovpv rollback
```

For a production server that already has OVPanel or other services, do **not** run the fresh installer blindly. Review the update/migration path first.

Documentation:

- [Installation](./docs/INSTALLATION.md)
- [Architecture](./docs/ARCHITECTURE.md)
- [Updates and rollback](./docs/UPDATES.md)
- [Renewal behavior](./docs/RENEWAL.md)
- [Feature matrix](./docs/FEATURE-MATRIX.md)
- [Roadmap](./ROADMAP.md)
## Architecture

```text
                         ┌──────────────────────────────┐
                         │        OV-PvNetwork         │
                         │       Panel / API / UI      │
                         └──────────────┬───────────────┘
                                        │
                    assignment / health / metrics / profile API
                                        │
             ┌──────────────────────────┼──────────────────────────┐
             │                          │                          │
      ┌──────▼──────┐            ┌──────▼──────┐            ┌──────▼──────┐
      │  OV-Node A  │            │  OV-Node B  │     ...    │  OV-Node N  │
      │  OpenVPN    │            │  OpenVPN    │            │  OpenVPN    │
      └─────────────┘            └─────────────┘            └─────────────┘

 Optional integrations:
 AnyConnect / ocserv · Mirza · Telegram · monitoring · bandwidth policies
```

## Requirements

| Component | Minimum | Recommended |
|---|---:|---:|
| Panel | 1 vCPU / 1 GB RAM / 10 GB | 2 vCPU / 2 GB RAM / 20 GB SSD |
| VPN node | 1 vCPU / 512 MB RAM / 5 GB | 1–2 vCPU / 1 GB+ RAM / 10 GB |

Supported installer targets: Ubuntu 22.04 LTS, Ubuntu 24.04 LTS and Debian 12 (best-effort where upstream package differences apply).
## Production-safe lifecycle

OV-PvNetwork treats changes as controlled operations rather than blind overwrites:

1. Run preflight checks.
2. Create a backup before an update.
3. Apply the target release and migrations.
4. Build and syntax-check the application.
5. Restart only the required control-plane service.
6. Verify local health.
7. Roll back when verification fails.

Node-side automation is designed to avoid flushing firewall rules or replacing unrelated routes/services. Always review a shared production node before deployment.

## Release policy

- `v1.0.0` is the stable baseline.
- Patch releases (`1.0.x`) are backwards-compatible fixes.
- Minor releases (`1.x.0`) add backwards-compatible capabilities.
- Major releases may contain breaking architecture/protocol changes.
- Production-visible changes must be documented in `CHANGELOG.md` and shipped through a tagged GitHub Release.

## Security

Never commit `.env`, databases, API/JWT secrets, SSH credentials, private keys, TLS material, client `.ovpn` profiles or real production screenshots. The public documentation uses sanitized demo values only.

See [SECURITY.md](./SECURITY.md) for reporting and deployment guidance.

## Credits

OV-PvNetwork is derived from and interoperates with the MIT-licensed OV-Panel / OV-Node projects by PrimeZ. Upstream attribution is preserved in [NOTICE.md](./NOTICE.md) and [LICENSE](./LICENSE).
