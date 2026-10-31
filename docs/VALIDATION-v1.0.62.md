# v1.0.62 candidate validation — PVN-1047

Scope: apply the existing administrator backup-retention setting in the real native timer/CLI path and recover stale, journal-owned PostgreSQL backup rehearsals. Preserve current customer state, pinned/referenced rollback checkpoints and active services. No UI, schema, VPN, routing or credential changes.

## Reproduction and focused evidence

The original native daily entrypoint calls make_backup directly. The earlier retention implementation runs only through web backup handlers; its comment that the timer visits the listing route is incorrect. A real synthetic SQLite backup reproduces the defect without any web request: an expired checkpoint survives. Five focused tests fail on the original Linux module; the zero-retention control passes.

The corrected candidate passes six initial Linux tests. An additional test then reproduces indefinite retention of known failed snapshot payloads; after correction, all nine focused Linux fixtures pass. Coverage includes:

- Real native snapshot and actual SQLite restore, followed by expiration without a web request.
- Retention zero disables deletion.
- At least three intact verified checkpoints, transaction references and pinned checkpoints survive.
- Unknown payloads and symlink targets survive; a corrupt current recovery journal blocks pruning.
- Stale recorded backup-only clone identities recover without FORCE; unrelated database identities and fresh journals are refused or preserved.
- Known expired failed snapshots are removed only after their temporary database has been recovered; unresolved recovery proof survives.

These fixtures use disposable databases/directories. The first Windows invocation hit existing POSIX durability/file-lock limitations; it is not a passing native result. The native class explicitly requires Linux. A pre-existing SQLAlchemy UTC deprecation warning is retained.

## Authorized operational checkpoint

Read-only host inspection found accumulated native snapshots, four interrupted backup-rehearsal databases and historical operator dependency caches. Recent daily backups were successful; no recent OOM event was found, so OOM is not asserted as the interruption cause.

A fresh native PostgreSQL backup completed an actual 33-table restore and five checksum checks before cleanup. Exact journal identities and zero connections were verified for the four disposable clones. Scoped cleanup recovered those clones and removed fourteen expired verified snapshots, freeing approximately5.7GB. Eight inactive, reconstructible dependency-cache directories freed approximately1.35GB more. Referenced caches, source archives, private deployment evidence, current/rollback releases and pinned backups were preserved.

Customer identity snapshots, environment/key/VPN configuration and protected service PIDs/restart counters matched before/after. No live customer rows were deleted and no panel/VPN/foreign service restarted. Exact paths, host inventory, identifiers and raw receipts remain private.

At this checkpoint the live application remains60. The earlier61 attempt rolled back when an independent guardian ended. No full61/62 application rollout is implied. Installation of the tested standalone lifecycle helper and its real repeat-backup verification remain pending exact-source CI and their own operational evidence.

## Remaining gates

Full exact-source CI, disposable PostgreSQL non-FORCE controls, immutable release/artifact gates and the limited helper installation remain pending. Do not infer these passes from the focused fixtures or cleanup result. Supported Stable remains37. Broader external-client, public ACME, assistive hardware and earlier partial security-scan limits are unchanged.

[English notes](RELEASE-NOTES-v1.0.62.md) · [یادداشت فارسی](RELEASE-NOTES-v1.0.62.fa.md) · [Incident](incidents/2026-10-31-native-backup-disk-growth.md)
