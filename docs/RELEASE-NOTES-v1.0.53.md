# v1.0.53 candidate — PVN-1037

Real native backup preparation refused an existing credential-key link before any deployment. Metadata-only inspection confirmed the canonical `/etc/pvnetwork-panel/anyconnect-credential-fernet.key` points to the older `/etc/pvnetwork/anyconnect-credential-fernet.key`: a regular root-owned 0600 file in a root-owned 0700 directory. Key contents were not printed, moved or regenerated.

The native backup/restore policy now recognizes only this exact alias. It checks root ownership of the link/target and every ancestor, rejects writable/linked ancestors, requires a private target directory and bounded private regular target, and refuses broken, redirected or custom configured paths. Backups store regular target bytes under the existing v2 logical key name. Same-host restore writes the checked target atomically, rechecks the alias before replacement and leaves the link intact. Ordinary canonical regular-key behavior remains unchanged. There is no database migration or UI change.

Ten root POSIX fixtures cover actual archive/restore and Fernet decryption, link identity, regular canonical keys, redirected/linked/missing targets, unsafe permissions/owners and changed aliases before restore. They run in the explicit root Linux CI gate. Windows ran eight applicable archive/version checks successfully and explicitly skipped the POSIX cases and Linux Bash execution; this is not a POSIX PASS. Compilation and frozen locks are separate checks. Exact CI and native backup/canary results remain pending.

This is same-host compatibility, not unattended cold-host migration. No live key, environment, service, node or customer row has been changed. Publication and the final scoped Production deployment remain gated. Code rollback reintroduces the old alias refusal, so keep a verified backup and the hardened recovery entry point.

Verified same-host restore also repairs a missing or empty legacy target under the same protected path while preserving the canonical link. Backup still refuses missing/empty target material. No operational key was modified for this test.
