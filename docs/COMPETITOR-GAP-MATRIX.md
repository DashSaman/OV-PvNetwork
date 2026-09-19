# PVNetwork Competitor Gap Matrix

Purpose: prevent useful capabilities discovered in competitor research from disappearing between sessions. `Gap` rows must map to a stable `PVN-xxx` task. `Already present` rows remain for parity evidence. `Deferred`/`Rejected` require a reason before implementation is skipped permanently.

> Research must be re-verified against current upstream documentation before claiming parity or implementing a competitor-derived feature. This matrix records known capability families, not a permanent statement that upstream projects never change.

## User lifecycle, device control and subscriptions

| Capability | Seen in / comparison source | PVNetwork | Task |
|---|---|---|---:|
| Expired renewal without recreation | internal requirement | Already present | PVN-002 |
| Finite preserve/reset/add traffic renewal | internal requirement | Already present | PVN-004 |
| Periodic traffic reset | Marzban / Xray panels | Gap | PVN-200 |
| Scheduled renewal | 3X-UI-like lifecycle tooling | Gap | PVN-201 |
| Multi-stage expiry alerts | modern control panels | Gap | PVN-202 |
| Traffic-threshold alerts | modern control panels | Gap | PVN-203 |
| Self-service user portal | Hiddify / Access Server-style UX | Gap | PVN-204 |
| Device inventory | Remnawave / HWID-oriented panels | Gap | PVN-206 |
| Device/session revoke | Remnawave / enterprise VPN | Gap | PVN-207 |
| HWID/device limit | 3X-UI / Remnawave | Gap | PVN-208 |
| Session history / terminate | enterprise VPN panels | Gap | PVN-209 / PVN-210 |
| QR connection outputs | Marzban / Hiddify / Xray panels | Gap | PVN-211 |
| User export/import | common admin panels | Gap | PVN-214 / PVN-216 |
| User groups and group policy | Access Server / Pritunl | Gap | PVN-221 / PVN-222 |
| Reseller scoped reports | commercial panel requirement | Gap | PVN-228 |
| User audit timeline | enterprise admin UX | Gap | PVN-229 |
| Grace period | billing-oriented panels | Gap | PVN-232 |
| Plan templates/catalog | commercial admin panels | Gap | PVN-235 / PVN-236 |
| Localized subscription page | Hiddify-style user UX | Gap | PVN-241 |
| Per-reseller subscription branding | multi-tenant panels | Gap | PVN-242 |
| Connection/download history | enterprise/admin portals | Gap | PVN-245 / PVN-246 |
| Multi-protocol identity | Marzban / Hiddify / Remnawave | Gap | PVN-248 |

## Nodes, fleet, routing and network policy

| Capability | Seen in / comparison source | PVNetwork | Task |
|---|---|---|---:|
| Multi-node OpenVPN assignment | current PVNetwork | Already present | baseline |
| Node health score | current PVNetwork | Already present | baseline |
| Maintenance / Drain / Resume | current PVNetwork | Already present | baseline |
| Controlled/canary fleet upgrade | current PVNetwork | Already present | baseline |
| Node capacity threshold | Remnawave/enterprise fleet patterns | Gap | PVN-300 |
| Admission control | large fleet patterns | Gap | PVN-301 |
| Node cost metadata | operations requirement | Gap | PVN-302 |
| Automatic unhealthy-node failover | multi-node panels | Gap | PVN-306 |
| Weighted assignment policy | load-balancing panels | Gap | PVN-307 |
| Geographic assignment policy | global VPN panels | Gap | PVN-308 |
| Latency-aware assignment | global VPN panels | Gap | PVN-309 |
| Host abstraction | Remnawave | Gap | PVN-312 |
| Reusable config profiles | Remnawave | Gap | PVN-313 |
| Node capability negotiation | protocol-aware panels | Gap | PVN-314 |
| Node version inventory | fleet managers | Gap | PVN-315 |
| Node rollback | fleet managers | Gap | PVN-317 |
| Config drift detection/reconciliation | enterprise fleet patterns | Gap | PVN-318 / PVN-319 |
| API-key/cert rotation | security lifecycle | Gap | PVN-320 |
| Deploy preflight / dry run | safe automation | Gap | PVN-322 / PVN-323 |
| Decommission workflow | fleet managers | Gap | PVN-325 |
| Node diagnostic bundle | support tooling | Gap | PVN-327 |
| Reachability tests | fleet managers | Gap | PVN-329 / PVN-330 |
| Split-tunnel policy UI | OpenVPN Access Server / VPN panels | Gap | PVN-339 |
| Per-user/group destination policy | Access Server / routing panels | Gap | PVN-340 |
| GeoIP / GeoSite management | Xray panels | Gap | PVN-341 / PVN-342 |
| Route import/export | Xray / enterprise panels | Gap | PVN-343 |
| Policy preview / canary / rollback | current bandwidth design pattern | Gap for routes | PVN-345 / PVN-346 / PVN-347 |
| WARP outbound | 3X-UI / Hiddify | Gap | PVN-352 |
| Custom outbound pools | 3X-UI / Xray panels | Gap | PVN-348 |
| Load balancing / failover rules | 3X-UI / Xray panels | Gap | PVN-349 / PVN-350 |
| Proxy chaining | Xray routing panels | Gap | PVN-351 |

## Observability, reporting and notifications

| Capability | Seen in / comparison source | PVNetwork | Task |
|---|---|---|---:|
| Live node CPU/RAM/traffic | current PVNetwork | Already present | baseline |
| Telegram monitoring | current PVNetwork | Already present | baseline |
| Prometheus endpoint | Remnawave / infrastructure tooling | Gap | PVN-400 |
| Official Grafana dashboard | infrastructure tooling | Gap | PVN-401 |
| Long-term node history | modern fleet panels | Gap | PVN-402 |
| Long-term user history | modern panels | Gap | PVN-403 |
| Top users/nodes analytics | admin panels | Gap | PVN-405 / PVN-406 |
| Peak/concurrency analytics | monitoring platforms | Gap | PVN-407 / PVN-408 |
| Health trend charts | fleet managers | Gap | PVN-409 |
| Alert history | monitoring platforms | Gap | PVN-410 |
| Central log viewer | modern control planes | Gap | PVN-411 |
| Structured audit viewer | enterprise panels | Gap | PVN-412 |
| Sanitized support bundle | enterprise support tools | Gap | PVN-414 |
| Scheduled reports | enterprise/admin panels | Gap | PVN-415 / PVN-416 |
| CSV / Excel / PDF reports | admin panels | Gap | PVN-417 / PVN-418 / PVN-419 |
| Traffic anomaly detection | observability tools | Gap | PVN-423 |
| Notification provider abstraction | scalable platform pattern | Gap | PVN-427 |
| Email notifications | enterprise panels | Gap | PVN-428 |
| Generic webhooks | many panels/integrations | Gap | PVN-430 |
| Slack/Discord-compatible webhook | integrations | Gap | PVN-431 |
| Notification templates | configurable panels | Gap | PVN-432 |
| Retry/delivery history | resilient notification systems | Gap | PVN-434 / PVN-435 |
| Synthetic node probe | observability tooling | Gap | PVN-438 |
| Public status page | SaaS/infra pattern | Gap | PVN-440 |

## Security and enterprise identity

| Capability | Seen in / comparison source | PVNetwork | Task |
|---|---|---|---:|
| TOTP 2FA | current PVNetwork / Access Server | Already present | baseline |
| Scoped API tokens | current PVNetwork | Already present | baseline |
| IP allowlist / rate limit | current PVNetwork | Already present | baseline |
| Granular RBAC | Access Server / enterprise products | Gap | PVN-500 |
| Custom roles/templates | enterprise products | Gap | PVN-501 / PVN-502 |
| OAuth2/OIDC | enterprise panels | Gap | PVN-503 |
| Passkey/WebAuthn | Remnawave / modern admin UX | Gap | PVN-504 |
| LDAP | OpenVPN Access Server | Gap | PVN-505 |
| RADIUS | OpenVPN Access Server | Gap | PVN-506 |
| SAML SSO | OpenVPN Access Server | Gap | PVN-507 |
| Admin session management/revoke | enterprise admin | Gap | PVN-508 / PVN-509 |
| Login history/security events | enterprise admin | Gap | PVN-511 / PVN-513 |
| Token last-used/rotation | security lifecycle | Gap | PVN-516 / PVN-517 |
| Backup encryption/signing | secure operations | Gap | PVN-521 / PVN-522 |
| CSP/security headers | web security baseline | Gap | PVN-524 / PVN-525 |
| Dependency vulnerability scan | modern CI | Gap | PVN-529 |
| SAST / secret scan / history scan | modern CI | Gap | PVN-531 / PVN-532 / PVN-533 |
| Screenshot privacy gate | public repository safety | Gap | PVN-534 |
| Tamper-resistant audit strategy | enterprise security | Gap | PVN-536 |
| 2FA recovery codes | enterprise identity | Gap | PVN-540 |
| DB least-privilege/read-only roles | enterprise deployment | Gap | PVN-544 / PVN-545 |

## Integrations and automation

| Capability | Seen in / comparison source | PVNetwork | Task |
|---|---|---|---:|
| Mirza integration | current PVNetwork | Already present | baseline |
| Generic signed outbound webhooks | modern control planes | Gap | PVN-600 / PVN-601 |
| Webhook retry/dead-letter | resilient integrations | Gap | PVN-602 |
| Billing provisioning templates | commercial panels | Gap | PVN-603 |
| Billing suspend/renew/top-up hooks | commercial panels | Gap | PVN-604 / PVN-605 / PVN-606 |
| Telegram management bot | Marzban / admin panels | Gap | PVN-607 |
| Telegram user renew/node actions | management bot pattern | Gap | PVN-608 / PVN-609 |
| Full Mirza lifecycle parity | internal integration | Gap | PVN-611 |
| API idempotency | reliable billing integrations | Gap | PVN-614 |
| Correlation IDs | observability/API quality | Gap | PVN-615 |
| API pagination/filter consistency | public API quality | Gap | PVN-616 / PVN-617 |
| API versioning | public API governance | Gap | PVN-618 |
| SDK generation | API ecosystem | Gap | PVN-620 |
| Admin CLI | operations tools | Gap | PVN-621 |
| Background jobs | slow node operations | Gap | PVN-623 |
| Offline-node retry queue | resilient fleet | Gap | PVN-624 |
| Scheduled jobs | lifecycle automation | Gap | PVN-625 |
| Job progress/cancel/retry UI | operations UX | Gap | PVN-626 / PVN-627 |

## Protocols and subscription formats

| Capability | Seen in / comparison source | PVNetwork | Task |
|---|---|---|---:|
| OpenVPN | current PVNetwork | Already present | baseline |
| Optional AnyConnect | current PVNetwork | Already present | baseline |
| WireGuard | Pritunl / universal VPN panels | Gap | PVN-700 |
| Xray core | Marzban / 3X-UI / Hiddify / Remnawave | Gap | PVN-701 |
| VLESS | Xray panels | Gap | PVN-702 |
| VMess | Xray panels | Gap | PVN-703 |
| Trojan | Xray panels | Gap | PVN-704 |
| Shadowsocks | Xray panels | Gap | PVN-705 |
| REALITY | 3X-UI / Xray panels | Gap | PVN-706 |
| Hysteria2 | Hiddify / modern universal panels | Gap | PVN-707 |
| TUIC | modern universal panels | Gap | PVN-708 |
| Sing-box | Hiddify / universal panels | Gap | PVN-709 |
| Protocol capability discovery | Remnawave-like architecture | Gap | PVN-711 |
| Raw/Base64 subscriptions | Xray ecosystem | Gap | PVN-714 |
| Xray JSON | Xray ecosystem | Gap | PVN-715 |
| Sing-box subscription | Sing-box ecosystem | Gap | PVN-716 |
| Clash/Mihomo subscription | proxy ecosystem | Gap | PVN-717 |
| User-Agent format negotiation | Remnawave / subscription systems | Gap | PVN-718 |
| Subscription template editor | Remnawave | Gap | PVN-719 |
| Subscription response rules | Remnawave | Gap | PVN-720 |
| Protocol-aware analytics | universal panels | Gap | PVN-723 |
| Fallback/multi-inbound | 3X-UI/Xray | Gap | PVN-727 / PVN-728 / PVN-729 |
| Geo asset updater | Xray ecosystem | Gap | PVN-731 |
| Protocol migration assistant | migration tooling | Gap | PVN-734 |

## Installation, update, HA and disaster recovery

| Capability | Seen in / comparison source | PVNetwork | Task |
|---|---|---|---:|
| Fresh install command | current release | Present but needs hardening | PVN-808 onward |
| `pvnetwork status` | desired ops UX | Gap | PVN-800 |
| `pvnetwork doctor` | desired ops UX | Gap | PVN-801 |
| backup/update/rollback CLI | desired ops UX | Partial | PVN-802 / PVN-803 / PVN-804 |
| Migration verification | safe upgrades | Gap | PVN-805 |
| Auto rollback on failed health | safe upgrades | Gap | PVN-806 |
| Stable/beta channels | release engineering | Gap | PVN-807 |
| Fresh install CI | Hiddify-like easy operations | Gap | PVN-808 |
| Disposable node deploy E2E | safe node automation | Gap | PVN-809 |
| Installer preflight/port conflicts | robust installers | Gap | PVN-810 / PVN-811 / PVN-812 |
| Existing-service safety check | Production requirement | Gap | PVN-813 |
| PostgreSQL/Nginx/TLS setup options | easy install | Gap | PVN-814 / PVN-815 / PVN-816 |
| Minimal firewall option | safe install | Gap | PVN-817 |
| Installer idempotency | Hiddify-style ops quality | Gap | PVN-818 |
| Node installer rollback | safe automation | Gap | PVN-821 |
| Signed/checksummed artifacts | release engineering | Gap/Partial | PVN-823 / PVN-824 |
| SBOM | supply-chain security | Gap | PVN-825 |
| DB migration backup/restore rehearsal | safe releases | Gap | PVN-827 / PVN-828 |
| PostgreSQL HA guide | enterprise deployment | Gap | PVN-829 |
| Control-plane HA guide | Access Server / enterprise patterns | Gap | PVN-830 |
| Disaster recovery runbook/test | enterprise operations | Gap | PVN-832 / PVN-833 |
| Upgrade-from-previous / rollback test | release engineering | Gap | PVN-836 / PVN-837 |
| Screenshot refresh workflow | docs/release quality | Gap | PVN-840 |
| Secret scan gate | public repo safety | Gap | PVN-842 |
| Required CI checks / branch protection | mature project governance | Gap | PVN-844 / PVN-843 |
| Compatibility matrix | release engineering | Gap | PVN-849 |

## Migration and ecosystem compatibility

| Capability | Source | PVNetwork | Task |
|---|---|---|---:|
| Import from Marzban | migration requirement | Gap | PVN-900 |
| Import from 3X-UI | migration requirement | Gap | PVN-901 |
| Import from Hiddify | migration requirement | Gap | PVN-902 |
| Import from Remnawave | migration requirement | Gap | PVN-903 |
| Generic OpenVPN CSV import | migration requirement | Gap | PVN-904 |
| Migration dry-run + rollback snapshot | safe migration | Gap | PVN-905 / PVN-906 |
| Legacy upstream-panel migration | project lineage | Gap | PVN-907 |
| Subscription compatibility checker | ecosystem | Gap | PVN-908 |
| Client compatibility matrix | ecosystem | Gap | PVN-909 |
| Karing / v2rayNG / V2Box / Mihomo tests | user ecosystem | Gap | PVN-910..913 |
| OpenVPN Connect / AnyConnect client tests | user ecosystem | Gap | PVN-914 / PVN-915 |
| Browser subscription tests | user ecosystem | Gap | PVN-916..918 |
| Translation coverage | internationalization | Gap | PVN-919 |
| RTL/LTR screenshot regression | UI quality | Gap | PVN-920 / PVN-921 |
| Public demo mode/data generator | public docs/testing | Gap | PVN-922 / PVN-923 |
| Sanitized documentation snapshot generator | public repo safety | Gap | PVN-924 |

## Comparison-source notes

- **Marzban** is a reference for Xray/multi-protocol lifecycle, subscriptions and management automation.
- **3X-UI** is a reference for broad Xray protocol/routing/outbound coverage and device/HWID-style controls.
- **Hiddify Manager** is a reference for easy install/update/backup and user-facing connection UX across modern protocols.
- **Remnawave** is a reference for host/config-profile abstractions, metrics, device/HWID, passkeys and subscription templating/rules.
- **OpenVPN Access Server** is a reference for enterprise identity, directory/SSO integrations, group policy and deployment operations.
- **Pritunl** is a reference for organizations/groups, route policy, SSO/audit and WireGuard-oriented VPN management.

The matrix is descriptive, not a feature ranking. PVNetwork should only implement a gap after confirming it fits the product scope and Production safety requirements.
