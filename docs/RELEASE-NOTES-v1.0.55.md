# v1.0.55 candidate — PVN-1039

The authorized v1.0.54 update stopped before activation because the panel's append-only `data/app.log` changed during the database snapshot. This patch excludes exactly that diagnostic output from restorable runtime and source archives. It does not delete or truncate the live log. Unknown `.log` files, SSH trust, credential keys and push keys remain covered by unchanged stability and checksum checks.

Real Linux synthetic tests reproduced the original exception, then passed the active-log backup with actual SQLite restore, changed-key refusal and unknown-log refusal after correction. No application UI, database schema, VPN, node, route or firewall behavior changes in this patch. Current v1.0.54 synthetic UI images describe the identical interface.

Final exact-commit CI, immutable artifact/public bootstrap, fresh native backup/canary and the owner-authorized limited panel deployment remain gates. This is QA, not a completed stable release. See [validation](VALIDATION-v1.0.54.md) for inherited evidence and explicit infrastructure limitations.
