# Native backup disk growth — PVN-1047

The real daily service executes the native backup CLI. The earlier retention policy was implemented only in web create/list handlers, so successful unattended backups accumulated without using the configured ten-day policy. A read-only inspection also found four old, durably recorded rehearsal databases from interrupted runs; subsequent backups did not recover them. The exact external interruption cause is not established. Recent daily backups completed successfully.

Historical operator staging dependency caches were a separate contributor. System journal/inode consumption did not explain the main host's largest allocations. No audit-history deletion, global Docker prune or live-database reclamation was used.

After a fresh actual-restored native backup, only exact journal-owned inactive rehearsal databases were recovered. Expired verified snapshots were pruned while preserving pins and recovery references. Proven inactive Python/Node dependency caches were removed after process/unit-reference and path/inode checks; referenced caches, source archives and deployment evidence survived.

The scoped operations freed approximately7GB in total. Customer identity/configuration hashes and critical service PIDs/restart counters matched, with no service restart. [Validation](../VALIDATION-v1.0.62.md) separates these actual operations from pending CI/helper/release gates. Private identifiers, backup copies, credentials and host paths remain outside Git.

The source correction moves automatic maintenance into the native backup path shared by the timer and CLI: configured retention, protected verified checkpoints, known failed-payload expiration and journal-owned non-FORCE rehearsal cleanup. Arbitrary database-name discovery is never a deletion criterion.
