<div align="center">

# PVNetwork Panel

**Production-oriented multi-node OpenVPN control plane with optional AnyConnect integration**

[![Version](https://img.shields.io/badge/version-1.0.6-brightgreen?style=flat-square)](./VERSION)
[![Ubuntu](https://img.shields.io/badge/Ubuntu-22.04%20%7C%2024.04-E95420?style=flat-square&logo=ubuntu&logoColor=white)](#requirements)
[![License](https://img.shields.io/badge/license-MIT-green?style=flat-square)](./LICENSE)

**English** · [فارسی](./README.fa.md)

</div>

## What changed in v1.0.6 vs v1.0.5

**PVN-027 — one online-user truth across Dashboard and Users.**

![v1.0.6 shared online truth dashboard](./docs/images/v1.0.6/en/desktop/online-truth-dashboard.png)

![v1.0.6 shared online truth users mobile](./docs/images/v1.0.6/en/mobile/online-truth-users.png) The panel now merges fresh central session heartbeats with a display-only direct-node fallback, deduplicates current PVNetwork users across nodes, and ignores orphan/stale node profiles in the global Online Users total. This fixes the case where a node could report live OpenVPN clients while its session hooks were missing from the central `active_sessions` view.

The fallback never writes enforcement sessions or changes device-limit behavior. Raw node/session metrics remain on node cards, while the global user count and User Management online flags are derived from the same shared user-presence snapshot. Transient node polling failures retain valid central state and a short cached direct snapshot.

Latest release: **v1.0.6** — [release notes](https://github.com/DashSaman/OV-PvNetwork/releases/tag/v1.0.6).

## What changed in v1.0.5 vs v1.0.4

**PVN-026 — choose target nodes while creating a user.** The Add User dialog now lists every known node, selects every currently available node by default, and keeps offline/draining/maintenance nodes visible but disabled. Operators can uncheck any available node before creation; the API persists the chosen assignment before remote provisioning and creates the profile only on the selected nodes.

![v1.0.5 Add User node selector desktop](./docs/images/v1.0.5/en/desktop/user-create-node-selector.png)

![v1.0.5 Add User node selector mobile](./docs/images/v1.0.5/en/mobile/user-create-node-selector.png)

Backward-compatible API calls that omit `node_ids` still resolve to all currently available nodes. Explicit assignments are authoritative: the periodic reconciler can repair missing profiles on selected nodes but cannot silently widen a user's node set. The selector is covered in English/Persian at phone, tablet and desktop widths.

Previous release: **v1.0.5** — [release notes](https://github.com/DashSaman/OV-PvNetwork/releases/tag/v1.0.5).

## What changed in v1.0.4 vs v1.0.3

**PVN-025 — PVNetwork brand purity and runtime ownership.** The tracked project now uses PVNetwork-owned application, service, package, storage and backup identifiers throughout. A blocking test scans every tracked text/path so the former upstream panel product identifier cannot return. Runtime naming is standardized on `/opt/pvnetwork-panel` and `pvnetwork-panel.service`, with safe compatibility for existing SQLite data and browser language preference.

The release also aligns API/package/frontend/release version metadata on **1.0.4** and changes installer/update resolution to the maintained `DashSaman/OV-PvNetwork` releases. Production migration is backup-first and uses a parallel local canary plus atomic proxy switch before retiring the previous runtime.

Previous release: **v1.0.4** — [release notes](https://github.com/DashSaman/OV-PvNetwork/releases/tag/v1.0.4).

## What changed in v1.0.3 vs v1.0.2

**PVN-205 — inline user quick edit.** The Users page now expands a safe quick editor from the row actions. Traffic limit, expiry (where policy allows), concurrent-device limit, active state, assigned nodes and an optional Reset Usage can be reviewed and applied without opening the full Edit modal. Username is intentionally read-only until the separate safe multi-node rename task (`PVN-022`) is implemented.

![v1.0.3 Quick Edit desktop](./docs/images/v1.0.3/en/desktop/users-inline-quick-edit.png)

![v1.0.3 Quick Edit mobile](./docs/images/v1.0.3/en/mobile/users-inline-quick-edit.png)

Node assignment changes are safety-gated: removed assignments are deactivated instead of deleting certificates, stale disabled profiles are reused where possible, and a newly selected unavailable node is rejected before mutation. Status/update synchronization is assignment-aware. Browser verification covers English LTR and Persian RTL on phone/tablet/desktop widths.

Previous release: **v1.0.3** — [release notes](https://github.com/DashSaman/OV-PvNetwork/releases/tag/v1.0.3).

PVNetwork Panel is the independently maintained PVNetwork control plane for multi-node OpenVPN operations, renewal, AnyConnect integration, monitoring, security controls, backup/restore, health scoring, traffic controls and safer deployment tooling.

> **Production safety is a project rule:** deployments are assumed live and under load. Changes use backup/check → narrow mutation → smallest necessary restart → health verification → rollback readiness. Public repository content is sanitized and must not contain live users, infrastructure identifiers or secrets.

## Visual tour

### Dashboard, users and nodes

![Dashboard, users and nodes](./docs/images/ui/01-control-plane.jpg)

### Administration, operations and security

![Administration, operations and security](./docs/images/ui/02-admin-security.jpg)

### Advanced fleet, monitoring and bandwidth controls

![Advanced fleet, monitoring and bandwidth controls](./docs/images/ui/03-operations.jpg)


### v1.0.2 Subscription mobile proof

![PVNetwork v1.0.2 Subscription desktop](./docs/images/v1.0.2/en/desktop/subscription.png)

![PVNetwork v1.0.2 Subscription mobile](./docs/images/v1.0.2/en/mobile/subscription.png)

v1.0.2 hardens the public Subscription page for small touch screens: notification, Linux-copy and AnyConnect-copy controls meet the mobile touch floor, long demo usernames/hosts wrap safely, and FA RTL / EN LTR remain overflow-safe.

### v1.0.1 desktop / mobile proof

![PVNetwork v1.0.1 desktop](./docs/images/v1.0.1/en/desktop/users.png)

![PVNetwork v1.0.1 mobile](./docs/images/v1.0.1/en/mobile/users-renew.png)

Detailed illustrated documentation:

- [Complete English UI guide](./docs/UI-GUIDE.md)
- [v1.0.1 Responsive & accessibility guide](./docs/RESPONSIVE-GUIDE.md)
- [راهنمای کامل فارسی رابط کاربری](./docs/UI-GUIDE.fa.md)
- [راهنمای فارسی Responsive و Accessibility](./docs/RESPONSIVE-GUIDE.fa.md)

## Core capabilities

| Area | Included |
|---|---|
| Users | Create with per-node selection, full edit, inline quick edit, activate/deactivate, delete, renewal, usage reset, node assignment, profile/subscription delivery |
| Renewal | Expired-user renewal, unlimited renewal, finite preserve/reset/add-traffic modes |
| AnyConnect | Per-user enable/disable, password generation/change, shared user identity |
| Multi-node | Node CRUD, health view, user assignment, safe node lifecycle |
| Fleet | Health score, maintenance, drain/resume, controlled upgrade/retry workflows |
| Monitoring | Realtime traffic dashboard, node CPU/RAM/uptime, Telegram monitoring plus explicit Node DOWN/UP transition alerts |
| Security | IP allowlist, rate limiting, TOTP 2FA, scoped/expiring API tokens |
| Operations | Bulk user actions, transfer/rebalance tools, usage history, audit/operational views |
| Bandwidth | Emergency off, policy preview/canary/activate, groups and per-node status |
| Backup | Verified manual backup download and guarded restore workflow |
| Integrations | Mirza integration API, OpenVPN node API, optional AnyConnect/ocserv hooks |
| v1.0.1 UX | Full mobile Main Admin navigation, viewport-safe dialogs, touch/focus/reduced-motion hardening, RTL/LTR responsive browser smoke matrix |

## v1.0.1 responsive behavior

Main Admin routes remain reachable on phones through Dashboard, Users, Nodes and a **More** menu containing Admins, Operations, Security, Fleet, Monitoring and Bandwidth. Shared CSS hardening keeps primary touch targets usable, dialogs inside the dynamic viewport, tables bounded to their own scroll region and long translated text able to reflow.

CI checks the major routes at `360`, `375`, `390`, `430`, `768`, `1024`, `1366`, `1440` and `1920` px in English LTR and Persian RTL. See [UX Audit](./docs/UX-AUDIT.md) and [Release QA Gate](./docs/QA-RELEASE-GATE.md).

## Quick installation

Run on a **fresh** supported server as `root`:

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/DashSaman/OV-PvNetwork/v1.0.5/install.sh)
```

The installer uses the tagged release source instead of following an unpinned development branch.

After installation, use the lifecycle manager where supported by the deployment:

```bash
pvnetwork status
pvnetwork doctor
pvnetwork version
pvnetwork backup
pvnetwork update
pvnetwork rollback
```

For a production server that already has a legacy panel deployment or other services, do **not** run the fresh installer blindly. Review the update/migration path, create a backup and verify the current service health first.

Documentation:

- [Installation](./docs/INSTALLATION.md)
- [Architecture](./docs/ARCHITECTURE.md)
- [Updates and rollback](./docs/UPDATES.md)
- [Renewal behavior](./docs/RENEWAL.md)
- [Feature matrix](./docs/FEATURE-MATRIX.md)
- [Competitor gap matrix](./docs/COMPETITOR-GAP-MATRIX.md)
- [Numbered capability backlog](./docs/FEATURE-BACKLOG.md)
- [Roadmap](./ROADMAP.md)

## Architecture

```text
                         ┌──────────────────────────────┐
                         │       PVNetwork Panel       │
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

1. Verify the current deployment and service health.
2. Create a backup before an update.
3. Apply only the target release and reviewed migrations.
4. Build and run automated checks.
5. Restart only the required control-plane service.
6. Verify local/public health and critical workflows.
7. Roll back immediately when verification fails.

Node-side automation must not flush firewall rules, replace default routes or remove unrelated services/tunnels simply to simplify deployment.

## Project governance

`AGENTS.md` is the persistent execution contract. Every applicable backlog item receives a stable `PVN-xxx` ID. The detailed registry covers UI/UX, user lifecycle, devices, node/fleet operations, observability, enterprise identity, automation, optional Xray/WireGuard protocol work, installer/HA/DR hardening and migration/client compatibility.

A task is not marked done merely because code exists; tests, build/compile, responsive/accessibility checks, repository sanitization and applicable Production health verification must pass first.

## Release policy

- `v1.0.0` remains the immutable stable baseline.
- `v1.0.1` adds compatible UX/responsive/governance hardening.
- Patch releases are backwards-compatible fixes.
- Minor releases add backwards-compatible capabilities.
- Major releases may contain breaking architecture/protocol changes.
- Production-visible changes must be documented in `CHANGELOG.md` and shipped through a tagged GitHub Release.

## Security

Never commit `.env`, databases, API/JWT secrets, SSH credentials, private keys, TLS material, client `.ovpn` profiles or real production screenshots. The public documentation uses sanitized demo values only.

See [SECURITY.md](./SECURITY.md) for reporting and deployment guidance.

## Credits

PVNetwork includes modifications derived from an MIT-licensed panel foundation and interoperates with the `primeZdev/ov-node` node component. Required attribution is preserved in [NOTICE.md](./NOTICE.md) and [LICENSE](./LICENSE).
