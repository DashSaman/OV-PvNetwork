# PVNetwork Panel v1.0.24 — Subscription runtime revived + MikroTik on-create panel fixed

`PVN-1009` repairs two live defects reported by the owner.

## Defect 1 — the public subscription page was completely inert
Since the v1.0.8 security hardening, `Content-Security-Policy: script-src 'self'` (without `'unsafe-inline'`) silently blocked every inline script of the `/sub` Jinja template: language and theme switching, copy buttons, the renewal countdown (forever stuck on "در حال محاسبه زمان باقی‌مانده..."), the AnyConnect copy helpers and the new QR overlay never executed. Additionally, nginx's `/sub-clients/` location overrides its `types{}` map, so the vendored QR library was served as `application/octet-stream` — under `nosniff` browsers refuse to execute it even where scripts were allowed.

## Fix 1
- The subscription page path now serves a dedicated CSP that adds `'unsafe-inline'` for scripts on that page only; the admin panel and every other path keep the strict policy untouched. Jinja autoescaping keeps reflected values inert.
- The QR library is served by the backend at `/sub-assets/qr/qrcode.js` with a correct JavaScript MIME type through the existing proxy — no nginx change.
- Migrating the template to a nonce/external-file architecture is registered as the follow-up task.

## Defect 2 — the Router/MikroTik on-create panel never appeared
`POST /users/` returned only the user's name as `data`, so the uuid extraction in the Add-User flow always failed and the credentials panel was unreachable.

## Fix 2
- `POST /users/` now returns `{"name": ..., "uuid": ...}` (the Add-User modal is its only consumer; legacy backends fall back to a name-based lookup).
- The results panel now shows each node's **server address** beside its one-time username/password, adds a per-node **Router profile download** button, and embeds a built-in **MikroTik/RouterOS step-by-step tutorial** (PPP → OVPN Client, Mode=IP, certificate import) in all 13 languages.

## Scope and safety
Backend middleware/app/users changes plus the admin frontend bundle and the subscription template. No OpenVPN, Node, Router listener, profile or session behavior changes; only `pvnetwork-panel.service` restarts.

## Release gate
Exact-head CI, focused contract tests, live browser verification of the subscription page (renewal countdown computed, QR overlay functional, QR library executed), sanitized artifact plus SHA256 publish and public re-download verification.
