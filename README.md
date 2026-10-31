# PVNetwork

**Current operations — PVN-1047:** [QA62 and the scoped helper deployment are verified](docs/PRODUCTION-v1.0.62.md). Native scheduled retention and stale rehearsal recovery are corrected; two real installed-entrypoint backups, customer/configuration/service preservation, exact-source CI and six public x86/ARM fresh/repeat guests pass. Scoped cleanup reclaimed about7GB on the panel host and lossless log compression about0.69GB on a node. The application remains60 after the earlier protective61 rollback; no full62 rollout or Stable promotion. Supported Stable remains37.

[فارسی](README.fa.md) · [Illustrated guide](docs/UI-GUIDE.md) · [Installation](docs/INSTALLATION.md) · [CLI](docs/CLI.md)

PVNetwork manages OpenVPN users, subscriptions, resellers and nodes from a multilingual web panel and a 25-item English/Persian operational console. The panel controls account policy; nodes provide VPN connectivity and report usage and session state.

## Release status and changes

**v1.0.62 verified public QA and scoped operational helper — PVN-1047.** Since QA61: automatic native backup retention, non-FORCE stale rehearsal recovery, protected restore sources and safe failed-payload expiry. Source certifi/follow-redirects locks also clear inherited audit blockers; the running application dependency environment is unchanged by helper-only activation. [English notes](docs/RELEASE-NOTES-v1.0.62.md) · [فارسی](docs/RELEASE-NOTES-v1.0.62.fa.md) · [Validation and limits](docs/VALIDATION-v1.0.62.md) · [QA release](https://github.com/DashSaman/OV-PvNetwork/releases/tag/v1.0.62). The illustrated interface is unchanged.

The earlier release checkpoints below retain their historical scope; the current operations status above supersedes their live-version/concurrency statements.

**v1.0.61 verified public QA — PVN-1045.** Since QA60: the subscription route uses explicit request/name/context for the pinned Starlette template API; six real synthetic route regressions and all12 source/tag CI checks pass, preserving200 rendering, escaped labels and404/assignment/offline behavior. Security60 dependency correction is retained. [Evidence](docs/VALIDATION-v1.0.61.md) · [English](docs/RELEASE-NOTES-v1.0.61.md) · [فارسی](docs/RELEASE-NOTES-v1.0.61.fa.md). The anonymous full archive and all six public native guests also pass. All four tag checks pass; separate backed-up activations remain pending the end of concurrent work, with live59 unchanged.

**v1.0.60 verified public QA — PVN-1046.** Since QA59: require patched aiohttp>=3.14.4 and update the frozen Web Push dependency; guarded transport and UI behavior stay unchanged. Source/tag checks, full audits/Web Push regression, anonymous archive and all six public x86/ARM fresh/repeat installations pass. [Evidence](docs/VALIDATION-v1.0.60.md) · [English notes](docs/RELEASE-NOTES-v1.0.60.md) · [فارسی](docs/RELEASE-NOTES-v1.0.60.fa.md) · [QA release](https://github.com/DashSaman/OV-PvNetwork/releases/tag/v1.0.60). Fresh backup/actual restore, rollback and live activation remain pending the end of concurrent work. Subscription PVN-1045 is separately fixed in61.

**v1.0.59 is verified public QA and active on the authorized panel — PVN-1044.** Since QA58: structured node errors now show readable messages with translated field labels in automatic installation and manual registration; raw validation input/context is excluded. Exact-source CI, anonymous assets, six public x86/ARM fresh/repeat guests and the backed-up Production activation pass. Four real deployed EN/FA schema-rejection cases confirm the message, focus and secret clearing. [English illustrated guide](docs/NODE-VALIDATION-v1.0.59.md) · [فارسی](docs/NODE-VALIDATION-v1.0.59.fa.md) · [Validation](docs/VALIDATION-v1.0.59.md) · [Production evidence](docs/PRODUCTION-v1.0.59.md) · [QA release](https://github.com/DashSaman/OV-PvNetwork/releases/tag/v1.0.59). Supported Stable remains v1.0.37; independent external node/client, public ACME and assistive hardware gates remain open. [Inherited subscription-route defect PVN-1045](docs/incidents/2026-10-19-subscription-template-contract.md).

**v1.0.58 is verified public QA.** Since QA57: rendered theme/scroll contrast, named node-weight fields and an accessible deployment console with cleared SSH secrets and verified-host guidance. Exact-source CI, 272 rendered states and official public fresh/repeat installation on all 6 x86/ARM distribution guests pass. [Illustrated guide](docs/MANUAL-ACCESSIBILITY-v1.0.58.md) · [فارسی](docs/MANUAL-ACCESSIBILITY-v1.0.58.fa.md) · [Evidence and remaining gates](docs/VALIDATION-v1.0.58.md) · [QA release](https://github.com/DashSaman/OV-PvNetwork/releases/tag/v1.0.58). At the QA58 checkpoint, the authorized panel ran v1.0.58; the later QA59 activation is recorded above. Supported Stable remains v1.0.37. [Production evidence and one inherited message limitation](docs/PRODUCTION-v1.0.58.md).

**v1.0.57 is verified public QA.** Since v1.0.56: native dialog focus/Escape/exact return, keyboard row/mobile menus, labels/headings/skip link, alerts, reduced motion and corrected light/focus/menu contrast. Exact CI, 228 axe scans and official fresh/repeat bootstrap on all 6 x86/ARM distribution guests passed. [Illustrated keyboard guide](docs/ACCESSIBILITY.md) · [راهنمای فارسی](docs/ACCESSIBILITY.fa.md) · [Evidence and remaining Stable gates](docs/VALIDATION-v1.0.57.md) · [QA release](https://github.com/DashSaman/OV-PvNetwork/releases/tag/v1.0.57). At the QA57 checkpoint, live remained v1.0.55; the later QA58 activation is recorded separately.

**v1.0.56 is verified public QA.** Since v1.0.55, new installer-managed HTTPS certificates record a safe successful-renewal Nginx reload hook. Exact CI, anonymous artifact verification and public fresh/repeat installation on all three distributions on x86_64 and real ARM64 passed. [Validation and remaining Stable gates](docs/VALIDATION-v1.0.56.md) · [English notes](docs/RELEASE-NOTES-v1.0.56.md) · [یادداشت فارسی](docs/RELEASE-NOTES-v1.0.56.fa.md). No new Production deployment or live certificate change occurred.

**v1.0.55 is verified QA, deployed through the owner-authorized limited panel update.** Its exact CI, public bootstrap on three distributions, native backup/canary and Production post-checks passed. The last supported stable release remains v1.0.37 pending broader mission gates. Read [validation evidence and limits](docs/VALIDATION-v1.0.55.md) and the target release notes before installing or updating.

Since v1.0.54: the native backup excludes only the panel's actively written diagnostic `data/app.log`; credential keys, SSH trust and other state retain their consistency checks. The log stays on the server. This resolves an update that stopped before activation. [English release notes](docs/RELEASE-NOTES-v1.0.55.md) · [تغییرات فارسی](docs/RELEASE-NOTES-v1.0.55.fa.md).

![PVNetwork dashboard — synthetic English Demo](docs/images/v1.0.54/en/desktop/dashboard.png)

The baseline tour uses 80 synthetic v1.0.54 captures, also applicable to v1.0.55–56. The [v1.0.57 keyboard guide](docs/ACCESSIBILITY.md) adds 4 current EN/FA mobile/desktop focus images and explains its light-modal changes. Images contain no customer/Production data and do not prove live service health.

## Start here

1. Review the [fresh-server requirements and access modes](docs/INSTALLATION.md). Choose Setup Mode for private evaluation or a real HTTPS domain for a remote-node controller.
2. Install on an eligible fresh server, read the private initial credentials and verify `sudo pvnetwork doctor --json`.
3. Follow [node installation](docs/NODE-INSTALLATION.md), then [create a user, download a profile and open the subscription](docs/UI-GUIDE.md#2-users).
4. Test an actual VPN connection and usage accounting on your test node before serving customers. A green panel or a downloaded profile alone does not prove tunnel connectivity.
5. Make a verified private backup and read [updates and recovery](docs/UPDATES.md) before changes to an existing installation.

The version-pinned QA command below is for **fresh-server evaluation using the published immutable v1.0.62 assets**. Do not use Fresh Install to replace an existing panel.

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/DashSaman/OV-PvNetwork/v1.0.62/install.sh)
```

The bootstrap verifies the official archive checksum and version, stages private tools/builds and verifies health before activation. Default Setup Mode is loopback-only; [the installation guide](docs/INSTALLATION.md) explains SSH forwarding and public TLS.

For an existing installation, start with `sudo pvnetwork update v1.0.62 --dry-run --json` and follow the [verified update/rollback guide](docs/UPDATES.md). Use the target only after its official assets and required gates are verified; Fresh Install is a different operation.

## Learn each section

| Section | What you can do | Tutorial |
| --- | --- | --- |
| Dashboard | Inspect live rates, counters, presence and node health | [Open](docs/UI-GUIDE.md#1-dashboard-and-navigation) |
| Users | Create, quick edit, renew, assign nodes, disable and delete | [Open](docs/UI-GUIDE.md#2-users) |
| Profiles and subscriptions | Download per-node profiles, use QR/client links, manage AnyConnect | [Open](docs/UI-GUIDE.md#3-profiles-subscriptions-and-anyconnect) |
| Nodes | Automatic SSH deployment, explicit adoption, manual registration, archives | [Open](docs/UI-GUIDE.md#4-nodes) |
| Admins / resellers | Set capacity and transfer account ownership | [Open](docs/UI-GUIDE.md#5-admins-and-resellers) |
| Operations | Review selected bulk actions, capacity transfer, history and rebalance | [Open](docs/UI-GUIDE.md#6-operations-center) |
| Security | Set access policy, TOTP, scoped tokens and staged panel settings | [Open](docs/UI-GUIDE.md#7-panel-security) |
| Fleet | Inspect node mode/version and manage scoped jobs | [Open](docs/UI-GUIDE.md#8-advanced-node-management) |
| Monitoring | Configure thresholds and private Telegram notifications | [Open](docs/UI-GUIDE.md#9-monitoring) |
| Bandwidth | Preview, canary and activate an emergency limit | [Open](docs/UI-GUIDE.md#10-bandwidth-control) |
| Backups | Create private archives and follow verified restore/recovery | [Open](docs/UI-GUIDE.md#11-panel-backup-and-restore) |
| CLI | Operate the 25-item EN/FA console and inspect jobs | [Open](docs/CLI.md) |

![Mobile users — synthetic Demo](docs/images/v1.0.54/en/mobile/users.png)

## Account behavior to understand

- Zero traffic quota denotes an unlimited plan with a 30-day baseline period; explicit device and node policies still apply.
- Renewal retains the user's UUID, name and assignments. Choose the usage mode deliberately.
- Safe rename, introduced in v1.0.16, invalidates old OpenVPN profiles immediately. Download and distribute replacement profiles after a successful rename.
- Presence is reported session state; cumulative traffic since boot is not the current connection speed.
- Node repair/reconciliation, deletion and code rollback have distinct scopes and guards. A queued job must reach a verified terminal state before it counts as successful.

## Operations and verification

```bash
sudo pvnetwork status --json
sudo pvnetwork doctor --json
sudo pvnetwork database check --json
sudo pvnetwork backup --json
sudo pvnetwork jobs --json
```

Ubuntu 22.04/24.04 and Debian 12 have exact v1.0.59 native fresh/repeat/public-bootstrap evidence on x86_64 and real ARM64. The authorized panel runs v1.0.59; sampled panel maintenance spanned 136.78 seconds. Complete customer identities, environment, key/configuration identities and protected service MainPIDs are preserved. [Production scope and actual UI checks](docs/PRODUCTION-v1.0.59.md). Public ACME, independent external VPS/client and real assistive hardware remain open. The sealed source 45 security assessment retains its partial coverage; existing 46/50 protections remain in 59. [Security closure and limits](docs/SECURITY-SCAN-CLOSURE.md).

## Documentation and security

- [English illustrated manual](docs/UI-GUIDE.md) · [راهنمای تصویری فارسی](docs/UI-GUIDE.fa.md)
- [Fresh installation](docs/INSTALLATION.md) · [نصب فارسی](docs/INSTALLATION.fa.md)
- [Nodes](docs/NODE-INSTALLATION.md) · [نودها](docs/NODE-INSTALLATION.fa.md)
- [CLI English](docs/CLI.md) · [کنسول فارسی](docs/CLI.fa.md)
- [Security policy](SECURITY.md) · [Changelog](CHANGELOG.md)
- [Release history](https://github.com/DashSaman/OV-PvNetwork/releases) · [Task ledger](AGENTS.md)

Keep backups, subscription links, VPN profiles, QR codes, API tokens and support diagnostics private. Use the repository's [security policy](SECURITY.md) when reporting a vulnerability. Replace all `.example.invalid`/Demo values in the guides with your own configuration privately.

## License and provenance

See [LICENSE](LICENSE) and the [node source and upstream notice](node-agent/README.md). Native node source provenance and license notices are retained in `node-agent/LICENSE` and `manifest.json`.
