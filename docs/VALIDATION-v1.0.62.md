# v1.0.62 candidate validation — PVN-1047

Scope: apply the existing administrator backup-retention setting in the real native timer/CLI path and recover stale, journal-owned PostgreSQL backup rehearsals. Preserve current customer state, pinned/referenced rollback checkpoints and active services. No UI, schema, VPN, routing or credential changes.

## Reproduction and focused evidence

The original native daily entrypoint calls make_backup directly. The earlier retention implementation runs only through web backup handlers; its comment that the timer visits the listing route is incorrect. A real synthetic SQLite backup reproduces the defect without any web request: an expired checkpoint survives. Five focused tests fail on the original Linux module; the zero-retention control passes.

The corrected candidate passed six initial Linux tests, then nine after known failed-payload coverage. Two additional controls reproduced deletion of a damaged old checkpoint and misclassification of a verified backup after a cleanup failure. Independent focused review then identified restore-source expiration during its safety backup and a missed failed SQLite rehearsal file. Both were reproduced and corrected: the restore journal protects its selected source, and known failed SQLite rehearsal payloads expire. All thirteen focused Linux fixtures pass, including an actual synthetic restore of an expired checkpoint. Coverage includes:

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

The first exact-source CI attempt passed all six fresh/repeat native installer jobs but failed both dependency-audit jobs on PYSEC-2026-4320 (alias GHSA-6q48-6c7w-9gw2), affecting the inherited certifi2026.7.22 lock. Both panel/node manifests now require certifi>=2026.10.19 and resolve only that dependency to2026.10.23. The upstream advisory recommends19 or later to retain unaffected emSign roots. Audits are not disabled or waived; fresh exact-source results remain required. This source dependency prerequisite does not imply the running panel environment has been upgraded.

A real empty PostgreSQL fixture also passed: recovery refused deletion while its test session was connected; the same session remained usable; deletion succeeded after closing that session. The fixture used no customer rows and was removed. This control ran under the native operation lock.

Full fresh exact-source CI, immutable release/artifact gates and the limited helper installation remain pending. Do not infer these passes from the focused fixtures or cleanup result. Supported Stable remains37. Broader external-client, public ACME, assistive hardware and earlier partial security-scan limits are unchanged.

The second CI attempt cleared dependency audits and passed six native guest jobs, but both main jobs failed the private Nginx certificate-activation fixture (750 tests, one failure). It overwrote certificate/key bytes on the same inode within one timestamp tick; [Nginx can inherit SSL objects when file index and modification time are unchanged](https://nginx.org/en/docs/ngx_core_module.html#ssl_object_cache_inheritable). The fixture now atomically replaces its synthetic files to model ACME activation. The real issuance hook and Production Nginx are unchanged; fresh full CI must verify this fixture correction.

[English notes](RELEASE-NOTES-v1.0.62.md) · [یادداشت فارسی](RELEASE-NOTES-v1.0.62.fa.md) · [Incident](incidents/2026-10-31-native-backup-disk-growth.md)
