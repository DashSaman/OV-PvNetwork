# PVNetwork Panel v1.0.3

**Patch task:** `PVN-205` — User profile/details + inline quick-edit row.

![Quick Edit desktop](./images/v1.0.3/en/desktop/users-inline-quick-edit.png)

![Quick Edit mobile](./images/v1.0.3/en/mobile/users-inline-quick-edit.png)

## What changed vs v1.0.2

- Added **Quick Edit** in the Users row actions.
- Edit traffic quota, expiry where policy permits, concurrent-device limit, Active state and assigned nodes in one place.
- Queue **Reset Usage** and apply the requested changes from the same panel.
- On phone/tablet, the editor becomes a full-width panel instead of inheriting the wide management table.
- Username remains read-only until the separately tracked safe multi-node rename (`PVN-022`) is implemented.

## Multi-node safety

Assignment removal deactivates the node-side profile rather than deleting the profile/certificate. Re-adding can reuse a stale disabled profile. A newly selected node that is offline, draining or in maintenance is rejected before mutation. User edits/status synchronization are assignment-aware.

## Verification

The release gate includes 37 Python/unit/governance tests, ESLint, Python compile, production Vite build, dependency audit/bundle budget, focused Quick Edit browser smoke, the full 2-language × 9-width × 9-route responsive matrix, Subscription responsive smoke, JSON/shell syntax and public secret/private-material guards.

## Upgrade and rollback

No database migration is required. Back up first. Deployment changes the panel/backend/frontend files only; do not alter firewall/default routes/tunnels or unrelated services. Restart only `pvnetwork-panel` if needed, then verify internal/public HTTP, OpenAPI and recent error logs. Roll back to the verified v1.0.2 backup/release if health checks fail.
