# PVNetwork Panel v1.0.2

**Patch scope:** PVN-111 — Responsive Subscription page.

![English desktop Subscription](./images/v1.0.2/en/desktop/subscription.png)

![English mobile Subscription](./images/v1.0.2/en/mobile/subscription.png)

## What changed
- Notification test, Linux copy and AnyConnect copy controls use a mobile 44px touch floor.
- Long demo usernames, hosts and credential values remain inside their cards.
- Automated Chromium smoke covers 360/375/390/430/768/1024/1440 px, Persian RTL and English LTR/theme switching.
- Public screenshots use only demo/example.invalid values.

## Upgrade / rollback
No database migration is required. Production deployment replaces only the Subscription template for this task and restarts only the panel service if template cache invalidation requires it. Keep the verified pre-deploy backup and restore the previous template/restart the panel if health verification fails.

## Safety
No intended firewall, default-route, tunnel, VPN-node, user identity or certificate changes.

[راهنمای فارسی](./RELEASE-NOTES-v1.0.2.fa.md)
