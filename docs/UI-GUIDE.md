# Illustrated UI Guide

All screenshots/diagrams in this public guide use synthetic data. No production user, hostname, IP address or credential is shown.

![Panel overview](./images/pvnetwork-ui-overview.svg)

## 1. Dashboard

The dashboard summarizes current users/nodes and service health. Use language/theme controls for presentation, Refresh for an immediate data reload and Logout to end the admin session. Node cards expose health, CPU/RAM, uptime, live network rate/traffic and online-session information when available.

## 2. User Management

![Users](./images/pvnetwork-users.svg)

The user screen provides search, sorting, pagination, account summary cards and row-level actions. The actions menu includes **Edit**, **Renew**, **Download**, **AnyConnect**, **Domain History** (authorized admin roles), **Reset Usage**, **Activate/Deactivate** and **Delete** where policy permits it. The copy icon copies the stable subscription link.

**Renew** extends the same account instead of delete/recreate. It preserves UUID, username, node assignments, subscription identity and existing AnyConnect identity. Finite plans can preserve usage, reset usage or add quota. Unlimited renewal only changes the time period.

**Reset Usage** on a finite plan resets shared traffic usage without changing expiry. On an unlimited plan it resets usage and starts a new 30-day period from the reset date, then re-enables the same identity on assigned nodes.

## 3. Node Management and Fleet

![Nodes and fleet](./images/pvnetwork-nodes.svg)

**Add Node** supports automatic SSH deployment. The deployment console shows staged progress and final verification. Operational actions include health review, Drain, Resume, Maintenance, Weight, retry/update/canary/rollback foundations and assignment-aware node operations. Rebalance workflows use node control/health state when moving assignments.

Node deletion must be treated as an assignment-sensitive operation. Never use node management as a reason to flush the full target firewall or blindly replace unrelated routes.

## 4. Admin / Reseller Management

Main-admin roles can create and manage reseller/admin accounts, traffic credit and unlimited-account entitlement. Reseller user actions are constrained by ownership and quota policy. Credit-changing actions are recorded in the reseller ledger.

## 5. Operations Center

The Operations Center exposes audit/event information and bulk operational workflows. Use it to inspect mutations, job outcomes, account/traffic summaries and cross-node actions. Bulk actions require confirmation and should be followed by a health/consistency check.

## 6. Panel Security

![Security and operations](./images/pvnetwork-security-ops.svg)

Security controls include TOTP/2FA, scoped API tokens, token expiry/revocation, request rate limiting and IP allow-list configuration. Rotate any credential that may have been exposed and keep secrets only in private deployment state.

## 7. Advanced Node / Fleet Controls

Fleet controls cover node health score, control state, staged/canary operations and rollback foundations. **Drain** prevents normal placement while allowing controlled transition; **Maintenance** excludes a node until explicitly resumed.

## 8. Monitoring

Monitoring settings cover node/service resource alerts and Telegram notification hooks. Metrics enrichment is designed to fail safely: a parser/optional metric failure must not make the core node health endpoint unavailable.

## 9. Bandwidth Control

Bandwidth controls target all users, an owner/reseller, a saved group or selected users. Preview the target set before applying a policy. Emergency policies can use duration/canary/fail-open behavior and should be reversible.

## Subscription page

The public subscription page shows account status, used/remaining traffic, expiry, concurrent-device limit, available server profiles, smart node recommendation, client downloads, AnyConnect details when enabled and renewal Web Push controls. Downloaded OpenVPN profiles are validated and may be rebuilt on demand if the stored profile is missing or invalid.

## Backup / Restore

Create a backup before risky production changes. Restore is a recovery mechanism, not a substitute for tested migrations and release verification.
