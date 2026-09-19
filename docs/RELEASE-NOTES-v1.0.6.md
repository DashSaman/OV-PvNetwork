# PVNetwork Panel v1.0.6 — Consistent Online-User Truth

**Patch task:** `PVN-027`

![Shared online-user truth — dashboard](./images/v1.0.6/en/desktop/online-truth-dashboard.png)

![Shared online-user truth — users mobile](./images/v1.0.6/en/mobile/online-truth-users.png)

## What changed vs v1.0.5

Dashboard and User Management now use one display-only online-user truth layer. Fresh central session heartbeats remain authoritative when present; a direct node `/sync/usage` snapshot fills display gaps when an older or misconfigured node is not reporting the same users into central session hooks.

- Online users are deduplicated by PVNetwork user UUID across nodes.
- Direct client names are mapped only when they match a current panel user and the exact node-name suffix.
- Orphan/stale node profiles do not inflate the global **Online Users** total.
- A user visible on multiple nodes is counted once globally; the per-user connection indicator keeps a lower-bound node-presence count when central session detail is missing.
- A short direct-node cache and bounded stale grace keep transient node timeouts from flashing known users offline.
- A failed node poll never removes valid fresh central session state.

## Enforcement safety

This patch is observability-only. It does **not** synthesize or write `active_sessions`, does not relax device limits, and does not change acquire/heartbeat/release enforcement. Raw per-node online/session metrics remain available on node cards; only the global user total is normalized to current PVNetwork users.

## Verification

The release includes unit tests for central/direct merge, cross-node deduplication, hyphenated usernames/node names, unknown clients, transient poll failure and stale-cache grace. A browser regression intentionally makes raw node counts sum to a different number than the shared user truth and requires Dashboard and User Management to render the same unique-user total in English/Persian on phone and desktop viewports.

## Upgrade / rollback

No database schema migration is required. Deployment changes panel backend/frontend code only. Back up the application and PostgreSQL first, validate a parallel local canary, switch the proxy atomically, and restart only `pvnetwork-panel.service` when moving the canonical backend. VPN nodes, routes, firewall rules, certificates and tunnels are outside this patch.
