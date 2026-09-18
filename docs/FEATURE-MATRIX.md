# PVNetwork Panel — Competitive Feature Matrix

Last reviewed: 2026-09-18

Sources used for competitor claims:
- Marzban: https://github.com/Gozargah/Marzban
- 3X-UI: https://github.com/MHSanaei/3x-ui
- Hiddify Manager: https://github.com/hiddify/Hiddify-Manager
- Remnawave: https://docs.rw/
- OpenVPN Access Server: https://openvpn.net/access-server/features/
- Pritunl: https://docs.pritunl.com/

Legend: ✅ built in, ◐ partial/different model, ❌ not currently provided.

| Capability | PVNetwork | Marzban | 3X-UI | Hiddify | Remnawave | OpenVPN AS | Pritunl |
|---|---:|---:|---:|---:|---:|---:|---:|
| Central multi-node control | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ cluster | ✅ replicated |
| OpenVPN user lifecycle | ✅ | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ |
| AnyConnect/ocserv identity | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Xray protocols | ❌ | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ |
| WireGuard | ❌ | ❌ | ✅ | ◐ | ◐ | ❌ | ✅ |
| Traffic quota + expiry | ✅ | ✅ | ✅ | ✅ | ✅ | ◐ | ◐ |
| Periodic quota reset | ❌ | ✅ | ✅ | ◐ | ◐ | ◐ | ◐ |
| Expired-user renewal without recreate | ✅ v1 blocker | ◐ | ✅ | ◐ | ◐ | ✅ | ✅ |
| Concurrent session limit | ✅ global | ◐ | ✅ IP/HWID | ◐ | ✅ HWID-oriented | ✅ | ✅ |
| Multi-node shared usage accounting | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Real-time node RX/TX dashboard | ✅ | ◐ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Health score / drain / maintenance | ✅ | ◐ | ◐ | ◐ | ✅ | ✅ | ✅ |
| Automatic user rebalance | ✅ | ❌ | ◐ | ◐ | ◐ | ✅ cluster | ✅ failover |
| Canary node upgrade / rollback | ✅ | ❌ | ◐ | ✅ auto-update | ◐ | ◐ | ◐ |
| Emergency per-user/group bandwidth policy | ✅ | ❌ | ◐ | ◐ | ◐ | ✅ policy | ✅ policy |
| Reseller traffic credit ledger | ✅ | ◐ | ◐ | ✅ admin roles | ◐ | ❌ | ❌ |
| Unlimited-account reseller slots | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| AnyConnect password rotation | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| User subscription page | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ client UI | ✅ client UI |
| QR/share links | ◐ | ✅ | ✅ | ✅ | ✅ | ◐ | ◐ |
| Multi-format subscriptions | ❌ | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ |
| Smart server recommendation | ✅ | ◐ | ◐ | ✅ | ◐ | ◐ | ✅ failover |
| Web Push renewal reminder | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Telegram monitoring | ✅ | ✅ bot | ✅ bot | ✅ bot | ◐ | ◐ | ◐ |
| Telegram management bot | ❌ | ✅ | ✅ | ✅ | ◐ | ❌ | ❌ |
| DNS domain activity per user | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Audit log | ✅ | ◐ | ◐ | ◐ | ✅ | ✅ | ✅ |
| TOTP admin MFA | ✅ | ◐ | ◐ | ◐ | ✅ | ✅ | ✅ |
| Scoped/expiring API tokens | ✅ | ◐ | ✅ | ◐ | ✅ | ✅ | ✅ |
| IP allowlist / rate limiting | ✅ | ◐ | ◐ | ◐ | ✅ | ✅ | ✅ |
| LDAP/RADIUS/SAML | ❌ | ❌ | ❌ | ❌ | ◐ | ✅ | ✅ |
| Passkey/WebAuthn | ❌ | ❌ | ❌ | ❌ | ✅ | ◐ | ◐ |
| Automatic backup | ◐ manual/scheduled infra | ✅ | ✅ | ✅ | ◐ | ✅ | ✅ |
| One-command install | ◐ v1 blocker | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| CLI doctor/update/rollback | ❌ v1 blocker | ✅ | ✅ | ◐ | ✅ | ✅ | ✅ |
| Prometheus/Grafana integration | ❌ | ◐ | ◐ | ◐ | ✅ | ✅ metrics | ✅ metrics |
| PWA admin panel | ❌ | ❌ | ✅ | ◐ | ◐ | ❌ | ❌ |
| PostgreSQL | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Bilingual/full documentation | ◐ v1 blocker | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |

## Current differentiators
PVNetwork is strongest where it combines OpenVPN operations with features uncommon in proxy panels: global multi-node session enforcement, AnyConnect credentials on the same user identity, reseller credit accounting, health/drain/rebalance operations, emergency bandwidth policy, per-user DNS-domain activity, and browser push renewal reminders.

## Important interpretation
Protocol breadth is not automatically a core deficit. Xray/VLESS/REALITY/WireGuard expansion should be treated as a product-direction decision. The v1.x priority is to make the current OpenVPN/AnyConnect control plane reproducible, observable, secure and easy to operate before adding unrelated cores.