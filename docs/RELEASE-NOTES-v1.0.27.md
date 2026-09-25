# PVNetwork Panel v1.0.27 — Firewall boot fix + 2FA recovery codes

`PVN-1001` + `PVN-540`.

## PVN-1001 — host firewall boot service
The boot service had failed on every boot since 2026-09-22: on Ubuntu 24.04 with socket-activated SSH, `ssh.service` remains inactive until the first connection, so the required-service gate always tripped and the inventory-first allowlist never applied. The gate now accepts `ssh.socket` / `sshd.service` as satisfying `ssh.service`. The hardening tool itself is unchanged: inventory-first backup, allowlist chain appended after every pre-existing rule (tunnels and source-specific rules keep precedence), and a timed automatic rollback unless health checks pass and the operator confirms.

## PVN-540 — one-time 2FA recovery codes
- Enabling TOTP now generates **eight recovery codes**, stored as bcrypt hashes (new `two_factor_recovery_codes` table, migration `g9a0b1c2d3e4`).
- Codes are shown **exactly once** in Security Settings with a copy-all button and a warning.
- If the authenticator app is unavailable, entering any unused code in the password-field of the login page (in place of the 6-digit code) logs you in and consumes that code.
- Disabling TOTP clears all codes; Security Settings shows the remaining count. All strings are translated in the 13 shipped languages.

## Scope and safety
No OpenVPN, Node, Router listener, profile or session changes. Only `pvnetwork-panel.service` restarts; the deployment also runs the Alembic migration after a verified database backup and (owner-authorized) re-runs the fixed firewall boot service, whose allowlist already covers every listener of the co-hosted services.

## Release gate
Exact-head CI, focused contract tests, backup-first migration, post-deploy health and service verification, sanitized artifact plus SHA256 publish and public re-download verification.
