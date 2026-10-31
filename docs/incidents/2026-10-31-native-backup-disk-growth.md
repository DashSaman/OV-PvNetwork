# Native backup disk growth — PVN-1047

The real daily service executes the native backup CLI. The earlier retention policy was implemented only in web create/list handlers, so successful unattended backups accumulated without using the configured ten-day policy. A read-only inspection also found four old, durably recorded rehearsal databases from interrupted runs; subsequent backups did not recover them. The exact external interruption cause is not established. Recent daily backups completed successfully.

Historical operator staging dependency caches were a separate contributor. System journal/inode consumption did not explain the main host's largest allocations. No audit-history deletion, global Docker prune or live-database reclamation was used.

After a fresh actual-restored native backup, only exact journal-owned inactive rehearsal databases were recovered. Expired verified snapshots were pruned while preserving pins and recovery references. Proven inactive Python/Node dependency caches were removed after process/unit-reference and path/inode checks; referenced caches, source archives and deployment evidence survived.

The scoped operations freed approximately7GB in total. Customer identity/configuration hashes and critical service PIDs/restart counters matched, with no service restart. [Validation](../VALIDATION-v1.0.62.md) records actual cleanup, exact-source CI, installed-helper checks and remaining external limits. Private identifiers, backup copies, credentials and host paths remain outside Git.

The source correction moves automatic maintenance into the native backup path shared by the timer and CLI: configured retention, protected verified checkpoints, known failed-payload expiration and journal-owned non-FORCE rehearsal cleanup. Arbitrary database-name discovery is never a deletion criterion.

The corrected helper is now active in its two existing locations. The actual timer entrypoint and CLI both completed new actual-restored backups; the first expired one eligible unreferenced checkpoint and the second did not remove more, both warning-free. Final checks found no rehearsal orphans, preserved customer/configuration/service state and verified rollback, with the application still60. [Production scope](../PRODUCTION-v1.0.62.md). A peer separately recovered about0.69GB through lossless closed-archive compression, with existing logrotate compatibility proven in disposable fixtures. An SSH-unreachable node remains uninspected pending owner access.
