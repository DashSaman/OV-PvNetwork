# v1.0.62 — verified native backup maintenance

Since QA61, the native scheduled/CLI backup path applies the configured retention policy before its free-space gate and after successful verification. It retains pinned/current-recovery checkpoints and at least three intact verified snapshots. Zero retention still disables pruning.

Before another backup, stale journal-owned backup rehearsal databases recover without terminating active database connections. Known failed snapshot payloads expire only after their recorded rehearsal is resolved. Unknown contents, symlinks and unrelated database identities remain protected.

This changes the operational lifecycle helper; schema, customer quotas/identities, VPN configuration and UI stay unchanged. Historical operator cache cleanup is a separately verified operation, not a global filesystem or Docker prune. Retire only proven unused reconstructible staging dependency trees after a completed rollout; retain source/evidence and anything referenced by a process or unit.

Damaged expired checkpoints survive for inspection; a cleanup failure is reported separately from a successfully verified snapshot. To clear inherited audit blockers, panel/node source locks use certifi2026.10.23 with a2026.10.19 minimum, and the frontend transitive follow-redirects lock uses1.16.2. Existing release artifacts and the running application environment are unchanged by a helper-only deployment.

[Verified tests and limits](VALIDATION-v1.0.62.md) · [Scoped activation, backup and rollback](PRODUCTION-v1.0.62.md) · [Illustrated interface](UI-GUIDE.md). Exact CI, six public guests and both installed-entrypoint backups pass; application stays60 and Stable is unchanged.
