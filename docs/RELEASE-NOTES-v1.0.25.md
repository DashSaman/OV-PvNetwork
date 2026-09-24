# PVNetwork Panel v1.0.25 — Router readiness probe + actionable credential errors

`PVN-1011` explains and fixes the "no username/password anywhere" report.

## Root cause
The v1.0.24 on-create Router flow was correct, but Router/MikroTik capability was never enabled on any node (the `node_router_openvpn` table was empty). Every credential request therefore failed with a bare 409 ("listener is not enabled on this node") and the results panel showed only errors — no credentials anywhere.

## What changed
- Ticking the Router/MikroTik checkbox in Add User now **probes the live Router status of every selected node** (`GET /router-openvpn/nodes/{id}`) and shows the verdict inline:
  - checking indicator while probing;
  - ready-node count (`Router-ready nodes: N/M`) in green;
  - a red step-by-step **enable instruction** when none are ready (Nodes page → the node → Router / MikroTik → run Preflight and Enable), stated before anything is submitted.
- Credential failures in the results panel translate into actionable messages: capability not enabled, listener unhealthy, or node needs upgrade — instead of raw 409 details.
- All new strings are translated in the 13 shipped languages; focused contract tests cover the probe, the hints and the error translation.

## Enabling Router on a node (operator steps)
1. Panel → Nodes → the target node → **Router / MikroTik**.
2. Run **Preflight**; if it passes, press **Enable** (the listener is isolated from the normal OpenVPN service and stays disabled per node until this step).
3. Retry Add User with the Router checkbox — the ready count should be green and one-time credentials will be generated and displayed with each node's server address, a profile download button and the RouterOS tutorial.

## Scope and safety
Admin frontend only. No API, authentication, OpenVPN, Node, Router listener, profile or session changes; deployment is an atomic frontend asset switch with no backend restart.

## Release gate
Exact-head CI, focused contract tests, atomic frontend deployment, public health and asset verification, sanitized artifact plus SHA256 publish and public re-download verification.
