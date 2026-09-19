# PVNetwork v1.0.1 Responsive & Accessibility Guide

This document complements the [complete illustrated UI guide](./UI-GUIDE.md) and explains how navigation, tables, dialogs and administrative workflows are expected to behave on desktop, tablet and mobile.

> Public screenshots use demo/sanitized data only. Production users, IPs, domains, UUIDs, secrets and credentials must never be exposed in repository imagery.

## Panel overview

**Desktop**

![Dashboard desktop](./images/v1.0.1/en/desktop/dashboard.png)

**Mobile**

![Dashboard mobile](./images/v1.0.1/en/mobile/dashboard.png)

v1.0.1 strengthens the shared layout from 360 to 1920 px: essential text must reflow instead of clipping, page-level horizontal overflow is blocked, and primary touch targets aim for at least 44×44 px.

## Users and daily actions

**Desktop**

![Users desktop](./images/v1.0.1/en/desktop/users.png)

**Mobile**

![Users mobile](./images/v1.0.1/en/mobile/users.png)

On phones, Search, Sort, Pagination and per-user actions stay reachable. Data tables may scroll inside their own container when the data is inherently tabular, but they must not push the whole page outside the viewport.

![User actions desktop](./images/v1.0.1/en/desktop/users-actions.png)

![User actions mobile](./images/v1.0.1/en/mobile/users-actions.png)

The three-dot action control now exposes proper menu semantics, is keyboard operable, closes with `Escape`, returns focus to the trigger and is repositioned to remain inside viewport edges.

## User renewal

![Renew desktop](./images/v1.0.1/en/desktop/users-renew.png)

![Renew mobile](./images/v1.0.1/en/mobile/users-renew.png)

The renewal dialog is viewport-bounded and internally scrollable on short screens. Header/footer controls remain reachable. The UX hardening does not alter the v1.0 renewal identity guarantees: UUID, username and existing assignments are preserved.

## AnyConnect

![AnyConnect](./images/ui/workflow-anyconnect.jpg)

Credentials and Copy/Change/Enable controls remain readable and touchable on narrow screens. Real security material is never included in public documentation.

## Nodes

![Nodes desktop](./images/v1.0.1/en/desktop/nodes.png)

![Nodes mobile](./images/v1.0.1/en/mobile/nodes.png)

Node health and Add/Edit/Download actions remain reachable on mobile. UI hardening must never justify changing a Production node's firewall, default route, tunnels or unrelated services.

![Add Node](./images/ui/workflow-add-node.jpg)

On narrow screens the Add Node flow stacks fields rather than compressing them beyond usability, while deploy progress remains visible.

## Main Admin mobile navigation

The bottom navigation keeps core destinations visible and moves the remaining administrative routes into a clear **More** menu:

```mermaid
flowchart TD
    A[Bottom Navigation] --> B[Dashboard]
    A --> C[Users]
    A --> D[Nodes]
    A --> E[More]
    E --> F[Admins]
    E --> G[Operations]
    E --> H[Security]
    E --> I[Fleet]
    E --> J[Monitoring]
    E --> K[Bandwidth]
```

No main administrative section is therefore available only from the desktop sidebar.

## Operations and Backup/Restore

![Operations desktop](./images/v1.0.1/en/desktop/operations.png)

![Operations mobile](./images/v1.0.1/en/mobile/operations.png)

Bulk actions, Transfer, Rebalance, Usage History and Audit stay reachable on smaller viewports. Restore remains a guarded destructive workflow requiring explicit confirmation.

## Security

![Security desktop](./images/v1.0.1/en/desktop/security.png)

![Security mobile](./images/v1.0.1/en/mobile/security.png)

TOTP, IP Allowlist, Rate Limit and scoped API Tokens remain usable on mobile. Keyboard focus is visible, and icon-only controls are required to expose accessible names.

## Fleet

![Fleet desktop](./images/v1.0.1/en/desktop/fleet.png)

![Fleet mobile](./images/v1.0.1/en/mobile/fleet.png)

Maintenance, Drain/Resume and Upgrade are sensitive operations. Their action groups wrap or stack at narrow widths without changing their meaning or safety semantics.

## Monitoring

![Monitoring desktop](./images/v1.0.1/en/desktop/monitoring.png)

![Monitoring mobile](./images/v1.0.1/en/mobile/monitoring.png)

Alert settings and Telegram test controls collapse to a readable single-column layout as needed. Loading, failure and Retry states remain explicit.
Node connectivity alerts can be toggled independently inside Monitoring Settings. Telegram sends a DOWN message only on an offline transition and a UP message only after recovery, avoiding repeated messages while the state is unchanged.


## Bandwidth Control

![Bandwidth desktop](./images/v1.0.1/en/desktop/bandwidth.png)

![Bandwidth mobile](./images/v1.0.1/en/mobile/bandwidth.png)

Preview, Canary, Activate and Emergency Off are intentionally distinct operations. On phones the action area expands for touch safety, while group/user/node pickers remain bounded inside the viewport.

## Release viewport matrix

Before an official release, the main routes are checked at `360`, `375`, `390`, `430`, `768`, `1024`, `1366`, `1440` and `1920` px. Core workflows are additionally reviewed for keyboard/touch operation and RTL/LTR behavior.

v1.0.1 CI runs a Chromium browser smoke matrix across all major routes and checks for page-level horizontal overflow and runtime errors. Browser CI complements rather than replaces Production validation; a live deployment still requires backup and health verification.

## Safe release workflow

```mermaid
flowchart LR
    A[Branch / Worktree] --> B[Tests]
    B --> C[Frontend Build]
    C --> D[Responsive Browser Smoke]
    D --> E[Secret / Public Data Scan]
    E --> F[Production Backup]
    F --> G[Minimal Deploy]
    G --> H[Health Verify]
    H -->|PASS| I[Git Tag + Release]
    H -->|FAIL| J[Rollback]
```

## Keyboard and accessibility behavior

- `Tab` reaches primary actions.
- Focus is shown with a visible outline.
- `Escape` closes an open row-actions menu.
- Non-essential motion is nearly removed under `prefers-reduced-motion`.
- Status meaning should not depend on color alone.
- Sensitive actions require clear confirmation and mutation feedback.

## Related documents

- [Complete English UI guide](./UI-GUIDE.md)
- [Release QA gate](./QA-RELEASE-GATE.md)
- [UX audit](./UX-AUDIT.md)
- [Numbered feature backlog](./FEATURE-BACKLOG.md)
- [راهنمای فارسی](./RESPONSIVE-GUIDE.fa.md)
