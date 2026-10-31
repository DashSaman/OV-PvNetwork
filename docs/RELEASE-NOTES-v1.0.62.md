# v1.0.62 candidate — bounded native backup maintenance

Since QA61, the native scheduled/CLI backup path applies the configured retention policy before its free-space gate and after successful verification. It retains pinned/current-recovery checkpoints and at least three intact verified snapshots. Zero retention still disables pruning.

Before another backup, stale journal-owned backup rehearsal databases recover without terminating active database connections. Known failed snapshot payloads expire only after their recorded rehearsal is resolved. Unknown contents, symlinks and unrelated database identities remain protected.

This changes the operational lifecycle helper; schema, customer quotas/identities, VPN configuration and UI stay unchanged. Historical operator cache cleanup is a separately verified operation, not a global filesystem or Docker prune. Retire only proven unused reconstructible staging dependency trees after a completed rollout; retain source/evidence and anything referenced by a process or unit.

Damaged expired checkpoints survive for inspection; a cleanup failure is reported separately from a successfully verified snapshot. To clear the inherited dependency-audit blocker, panel/node source locks use certifi2026.10.23 with a2026.10.19 minimum. Existing release artifacts and the running application environment are unchanged by a helper-only deployment.

[Actual tests, cleanup and pending gates](VALIDATION-v1.0.62.md) · [Existing illustrated interface](UI-GUIDE.md). At the initial checkpoint the application stays60; the full62 application is not deployed or promoted to Stable.
