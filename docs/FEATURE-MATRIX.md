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
| Expired-user renewal without recreate | ✅ | ◐ | ✅ | ◐ | ◐ | ✅ | ✅ |
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
| Automatic backup | ◐ | ✅ | ✅ | ✅ | ◐ | ✅ | ✅ |
| One-command install | ✅ v1.0.0 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Prometheus/Grafana integration | ❌ | ◐ | ◐ | ◐ | ✅ | ✅ metrics | ✅ metrics |
| PWA admin panel | ❌ | ❌ | ✅ | ◐ | ◐ | ❌ | ❌ |
| PostgreSQL | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Bilingual illustrated documentation | ✅ v1.0.0 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |

## Current differentiators

PVNetwork combines OpenVPN operations with global multi-node session enforcement, optional AnyConnect credentials on the same user identity, reseller credit accounting, health/drain/rebalance controls, emergency bandwidth policy, per-user DNS-domain activity and browser push renewal reminders.

## Interpretation

Protocol breadth is a separate product-direction decision. Xray/VLESS/REALITY/WireGuard expansion is planned as an optional later major direction; v1.x prioritizes hardening and operating the current OpenVPN/AnyConnect control plane.
