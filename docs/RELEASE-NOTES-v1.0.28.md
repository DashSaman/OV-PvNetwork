# PVNetwork Panel v1.0.28 — Renewal notifications (expiry + traffic)

`PVN-202` + `PVN-203`.

## What it adds
The Telegram monitor now sends **renewal alerts** for active users, alongside the existing node DOWN/UP and CPU/RAM/disk alerts:

- **Expiry stages** — 7, 3, 1 and 0 days before expiry. Only the nearest applicable stage fires per run, so a user never gets three messages on the same day.
- **Traffic thresholds** — 80, 90 and 100 percent of the user's quota (highest crossed stage only). Unlimited accounts are ignored.

## Delivery and dedup
- Delivered through the existing Monitoring Settings (same bot token, chat and enable toggle) — nothing new to configure.
- Alert keys (`renew:e:<user>:<stage>` / `renew:t:<user>:<stage>`) flow through the same persisted transition state as node alerts: a condition notifies **once** when it appears and clears **silently** when the user renews or the usage resets, then can fire again on the next cycle.
- Inactive users are skipped entirely.

## Scope and safety
Backend monitor only (new `backend/operations/renewal_alerts.py` wired into `telegram_monitor.py`). No API, auth, OpenVPN, Node, Router listener, profile or session changes; only `pvnetwork-panel.service` restarts.

## Release gate
Exact-head CI, focused unit tests for stages, thresholds, transitions and wiring, Production deployment with post-deploy health verification, sanitized artifact plus SHA256 publish and public re-download verification.
