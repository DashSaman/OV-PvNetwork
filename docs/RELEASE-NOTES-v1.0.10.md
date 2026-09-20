# PVNetwork Panel v1.0.10 — Backward-Compatible Protocol Alias Migration

`PVN-030` moves the remaining PVNetwork-owned protocol aliases away from legacy names without cutting off existing Nodes or API integrations.

## Compatibility behavior

- Newly created API tokens use `pvn_`; existing `ovp_` tokens continue to authenticate and receive the same scope checks.
- Node callbacks may send `X-PVNetwork-Node-Key` or the legacy `X-OV-Node-Key`.
- When both node-key headers are present with the same value, the request is accepted. If their values differ, the request is rejected with HTTP 400.
- Node upgrade patches inject `_pvnetwork_*` dashboard/online helpers and normalize older `_ov_*` helper aliases during an upgrade.

## Intentionally unchanged

- `primeZdev/ov-node`, `/opt/ov-node` and `ov-node.service` remain upstream-owned compatibility identifiers.
- Existing Nodes do not require an immediate upgrade.
- The normal OpenVPN listener, PKI, client profiles and certificate-only authentication flow are unchanged.

## Verification

The release gate includes protocol compatibility tests, the full Python suite, compile/static checks, frontend lint/build/audit, browser regression tests, secret scanning and a Production canary before rollout.
