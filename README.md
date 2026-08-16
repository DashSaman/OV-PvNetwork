<div align="center">

# OV-PvNetwork

**Production-oriented multi-node VPN control plane for OpenVPN with optional AnyConnect integration**

[![Version](https://img.shields.io/badge/version-1.0.0--rc1-orange?style=flat-square)](./VERSION)
[![Ubuntu](https://img.shields.io/badge/Ubuntu-22.04%20%7C%2024.04-E95420?style=flat-square&logo=ubuntu&logoColor=white)](#requirements)
[![License](https://img.shields.io/badge/license-MIT-green?style=flat-square)](./LICENSE)
[![Upstream](https://img.shields.io/badge/upstream-OV--Panel-blue?style=flat-square)](https://github.com/primeZdev/ov-panel)

**English** · [فارسی](./README.fa.md)

</div>

---

OV-PvNetwork is a production-derived distribution and operations layer built on top of the open-source OV-Panel / OV-Node ecosystem. It keeps the simple OpenVPN user-management workflow while adding the operational pieces we needed in a real multi-node deployment: node automation, reconciliation, safer profile delivery, real NIC telemetry, realtime admin monitoring, branded subscriptions, health checks, update/rollback tooling, and integration hooks for additional VPN/control-plane components.

> This repository intentionally pins upstream components instead of blindly tracking `latest`. The current base is OV-Panel `v1.7.10`, OV-Node `v1.3.6`, and the OpenVPN installer commit recorded in `manifest.json`.

## Quick install

Run on a fresh supported server as `root`:

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/DashSaman/OV-PvNetwork/main/install.sh)
```

The installer performs preflight checks, installs the pinned base, creates a backup/rollback point, builds the frontend, installs the OV-PvNetwork manager and production services, then verifies the local API before declaring success.

After installation:

```bash
ovpv status
ovpv doctor
ovpv update
ovpv backup
ovpv rollback
```

## What is different from upstream OV-Panel?

- Multi-node OpenVPN operation with desired-state user assignment.
- Low-impact user/node reconciler with systemd timer.
- Node auto-deploy foundation and pinned OV-Node/OpenVPN dependencies.
- Self-healing `.ovpn` generation and strict profile validation.
- Database-controlled `remote`, protocol and OpenVPN port normalization at download time.
- Real NIC counters (`rx_bytes`, `tx_bytes`, interface, uptime and cumulative traffic).
- Realtime admin dashboard designed around one aggregated backend request, overlap protection and hidden-tab pause.
- Server-side/per-node traffic-rate model to avoid browser/cache timing spikes.
- Subscription-side smart node comparison with user-page sampling only on page load.
- Safe node lifecycle controls, including assignment-aware removal.
- Production health checks, recovery timers, backup and rollback tooling.
- Private Network branding, favicon and subscription/client-download experience.
- Telegram/GitHub project links and multilingual panel UI foundation.
- Integration hooks used by the production deployment for AnyConnect/session control, bandwidth controls, monitoring, domain activity and fleet operations.

See [docs/FEATURES.md](./docs/FEATURES.md) for the detailed feature/status matrix.

## Requirements

### Panel server

| Profile | CPU | RAM | Disk | Use case |
|---|---:|---:|---:|---|
| Minimum | 1 vCPU | 1 GB | 10 GB | Lab / very small deployment |
| Recommended | 2 vCPU | 2 GB | 20 GB SSD | Normal production |
| Busy control plane | 4 vCPU | 4 GB+ | 40 GB+ SSD | Many users/nodes/monitoring |

### VPN node

| Profile | CPU | RAM | Disk |
|---|---:|---:|---:|
| Minimum | 1 vCPU | 512 MB | 5 GB |
| Recommended | 1–2 vCPU | 1 GB+ | 10 GB+ |

Network throughput depends far more on the provider, CPU crypto performance, MTU/routing and the number of concurrent VPN sessions than on disk size.

Supported installer targets:

- Ubuntu 22.04 LTS
- Ubuntu 24.04 LTS
- Debian 12 (best-effort where upstream packages differ)

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

 Optional production integrations:
 AnyConnect / session control · monitoring · bandwidth policies · domain activity
```

More detail: [docs/ARCHITECTURE.md](./docs/ARCHITECTURE.md).

## Updates and rollback

OV-PvNetwork treats updates as a transaction:

1. Preflight and free-space check.
2. Backup configuration/data/source metadata.
3. Fetch target release/channel.
4. Apply versioned overlay/migrations.
5. Build and syntax-check.
6. Restart only the control-plane service when required.
7. Run health verification.
8. Roll back automatically/manual if verification fails.

Read [docs/UPDATES.md](./docs/UPDATES.md).

## Production snapshot workflow

The live project accumulated changes over multiple production phases. To avoid pretending that a reconstructed patch is identical to the running system, this repo includes a sanitised production-export workflow. It captures source/configuration structure while explicitly excluding databases, private keys, `.env` secrets, certificates, user profiles and logs.

See [docs/PRODUCTION-SNAPSHOT.md](./docs/PRODUCTION-SNAPSHOT.md).

## Security notes

- Never commit `.env`, databases, API keys, JWT secrets, private keys, client `.ovpn` profiles, SSH credentials or TLS material.
- Use a firewall and expose only required ports.
- Keep the panel behind TLS/reverse proxy for Internet-facing deployments.
- Node API keys must be unique and rotated if exposed.
- Automatic node deployment requires privileged SSH access; use it only from a trusted panel host.

See [SECURITY.md](./SECURITY.md).

## Project links

- GitHub: `https://github.com/DashSaman/OV-PvNetwork`
- Telegram bot: `https://t.me/pvnetwork_bot`
- Upstream OV-Panel: `https://github.com/primeZdev/ov-panel`
- Upstream OV-Node: `https://github.com/primeZdev/ov-node`

## Credits

OV-PvNetwork is derived from and interoperates with the MIT-licensed OV-Panel / OV-Node projects by PrimeZ. Upstream attribution is preserved in [NOTICE.md](./NOTICE.md) and [LICENSE](./LICENSE).

## Status

`1.0.0-rc1` is the repository/bootstrap release. The production-snapshot workflow exists specifically so the public stable release can be built from the actual running source rather than from memory or a partial reimplementation.
