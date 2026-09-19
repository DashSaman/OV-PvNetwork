# PVNetwork Panel v1.0.5 — PVN-026 User-Creation Node Selector

## What changed

The Add User workflow now makes node placement explicit. Every currently available node is selected by default, while offline, draining and maintenance nodes remain visible but disabled. Operators may uncheck available nodes before submitting the form, and the backend provisions the new OpenVPN identity only on the persisted selection.

![Desktop node selector](./images/v1.0.5/en/desktop/user-create-node-selector.png)

![Mobile node selector](./images/v1.0.5/en/mobile/user-create-node-selector.png)

## Backend contract

- `CreateUser.node_ids` is optional for backward compatibility.
- Omitted `node_ids` resolves to all nodes that are active, not draining and not in maintenance.
- Explicit node IDs are validated before user creation or reseller-entitlement changes.
- Desired assignments are written in the same database transaction as the new user and optional AnyConnect credential state.
- Remote provisioning happens only after that transaction commits and only against the stored assignment.
- Temporary node failures do not roll back a valid user record; the scheduled reconciler can repair the missing profile later.

## Reconciler behavior

Explicit assignment rows are authoritative. The reconciler no longer creates extra `user_nodes` rows and therefore cannot silently widen a selected node set. Legacy users that predate explicit assignments keep the historical all-available fallback. Drain/maintenance nodes are excluded from reconciliation work.

## Verification before Production

- Focused user-creation/assignment/Quick Edit/brand regression: 32/32 PASS.
- Full Python unit/governance suite: 58/58 PASS.
- Python/shell/JSON syntax and `uv lock --check`: PASS.
- Frontend ESLint + production build: PASS.
- Runtime npm audit: 0 vulnerabilities; largest JS bundle remains within the CI budget.
- Node-selector browser smoke: PASS in English and Persian at 360/390/768/1440 px.
- Existing full responsive, Quick Edit and Subscription browser gates: PASS.

## Production safety

No database migration is required. Production deployment must use the project-standard verified backup, exact-commit canary, narrow application/frontend cutover, minimal panel restart, local/public health verification and rollback-ready evidence. VPN routing, firewall, tunnels, node certificates and unrelated services are outside this release.
