# PVNetwork Panel v1.0.23 — Smart subscription page: QR codes and per-device guides

`PVN-211` is the first item of the owner-approved five-release track recorded in `ROADMAP.md`.

## What it adds
- **Page QR** — a button in the Servers section renders a QR of the subscription page URL, so a user can open their subscription on a phone by scanning.
- **Per-server QR** — every online server row gains a QR button that renders that server's config download URL; scanning it on a mobile device opens the `.ovpn` download directly. The button stops the anchor navigation so the row still works as a normal download link.
- **Per-device quick-connect guide** — six cards (Windows, macOS, iPhone/iPad, Android, Linux, MikroTik/Router) with concrete steps in Persian and English, including the Router/MikroTik credential flow introduced in v1.0.21.

## How QR rendering works
- Codes are generated entirely client-side by the vendored MIT-licensed `qrcode-generator` (Kazuhiko Arase), served same-origin from `/sub-clients/qr/qrcode.js`.
- No CDN, no external requests, CSP-compatible (`script-src 'self'`); attribution is recorded in `NOTICE.md`.
- A modal overlay with keyboard (Escape/Enter) and click-outside closing; rendering failures degrade to a visible error instead of a broken panel.

## Scope and safety
Template and one static asset only. No API, authentication, database, OpenVPN, Node, Router listener, profile or session changes. Deployment copies the template plus the vendored script and restarts only `pvnetwork-panel.service`.

## Release gate
Exact-head CI, template contract tests (`tests/test_subscription_qr.py`), local/public verification of the subscription page and the static asset, sanitized artifact plus SHA256 publish and public re-download verification.
