# PVN-1037 / 1.0.53: existing key alias recovery

Real native backup preparation refused an existing canonical key symlink. Metadata only (no key value) confirms the exact older PVNetwork state target is root-owned, regular, 0600, under a root-owned 0700 directory. Do not flatten, move, rotate or regenerate this working key to satisfy the guard.

Support only the fixed canonical-to-legacy alias, validating link ownership, every ancestor, private target directory and root-owned private regular target. Keep arbitrary custom key paths and redirected/unsafe/broken aliases rejected. Archive the target as regular bytes under the existing v2 logical key name. Same-host restore writes the verified legacy target atomically and leaves the alias intact; a regular canonical key retains its existing behavior. This is same-host compatibility, not a claim of unattended cold-host migration.

First reproduce the current refusal using real POSIX links. Test actual archive/decrypt/restore preservation, ordinary canonical keys and rejection of redirect, writable ancestor, wrong owner, permissive mode and broken links. Run root fixtures in explicit CI, adjacent lifecycle regressions and exact fresh matrix. Prepare a new verified native backup/canary before requesting final scoped Production deployment.
