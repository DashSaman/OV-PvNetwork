# PVNetwork Panel v1.0.26 — Router password viewable in the admin panel

`PVN-1012` makes Router/MikroTik passwords viewable in the admin panel at the owner's request.

## What changed
- Router credentials now store a **reversible Fernet ciphertext** of the password (`password_ciphertext`, encrypted with the panel secret via the existing `encrypt_secret` helper — the same storage pattern AnyConnect already uses). The node-side verifier still receives only the one-way hash.
- The user Router/MikroTik dialog in the admin panel shows the **current password** beneath the username whenever a stored copy exists, so an operator no longer has to save it at generation time.
- Credentials created before this release have no stored copy; the dialog shows a hint to press **Rotate credentials** once, after which the password becomes viewable.
- The on-create one-time warning now states that the password also remains viewable in the admin panel (translated in all 13 languages).

## Security notes
- Display requires an authenticated admin/reseller API session (`get_current_user`), identical to every other Router management endpoint; the public subscription page and node callbacks never receive the plaintext.
- The ciphertext is keyed from `JWT_SECRET_KEY` — rotating that secret invalidates stored plaintext recovery (credentials keep working via their on-node hashes).
- An Alembic migration (`f8a9b0c1d2e3`) adds the nullable column; no existing row is rewritten.

## Scope and safety
Panel-only feature. No OpenVPN, Node, Router listener, profile or session behavior changes; only `pvnetwork-panel.service` restarts. The deployment runs the migration after a verified database backup.

## Release gate
Exact-head CI, focused contract + crypto round-trip tests, backup-first migration on Production, post-deploy health and endpoint verification, sanitized artifact plus SHA256 publish and public re-download verification.
