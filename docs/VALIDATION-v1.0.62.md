# v1.0.62 verified scoped validation — PVN-1047

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

At this checkpoint the live application remains60. The earlier61 attempt rolled back when an independent guardian ended. No full61/62 application rollout is implied. The tested standalone helper is now installed and its actual timer/CLI repeat-backup verification passed; [the operational record](PRODUCTION-v1.0.62.md) documents the exact scope and rollback readiness.

## Final verification and retained limits

The first exact-source CI attempt passed all six fresh/repeat native installer jobs but failed both dependency-audit jobs on PYSEC-2026-4320 (alias GHSA-6q48-6c7w-9gw2), affecting the inherited certifi2026.7.22 lock. Both panel/node manifests now require certifi>=2026.10.19 and resolve only that dependency to2026.10.23. The upstream advisory recommends19 or later to retain unaffected emSign roots. Audits are not disabled or waived; final exact-source results are recorded below. This source dependency prerequisite does not imply the running panel environment has been upgraded.

A real empty PostgreSQL fixture also passed: recovery refused deletion while its test session was connected; the same session remained usable; deletion succeeded after closing that session. The fixture used no customer rows and was removed. This control ran under the native operation lock.

Final source `cd305783f4b0836bb0f1416a004ca55ddbe5b607` passed both [push CI](https://github.com/DashSaman/OV-PvNetwork/actions/runs/41219984230) and [PR CI](https://github.com/DashSaman/OV-PvNetwork/actions/runs/41219988028), all eight checks. Each full suite passed752 unit/governance tests (80 explicit skips),82 root fixtures,38 security regressions,37 router controls, an actual isolated VPN handshake, build/lint/runtime audits and browser/accessibility checks. Existing incomplete/manual classifications remain; no full assistive-hardware certification is claimed. [All six public x86/ARM fresh/repeat guest receipts](evidence/v1.0.62-public-native.json), anonymous complete archive/checksum and the [scoped installed-helper operation](PRODUCTION-v1.0.62.md) also PASS. Stable remains37; external-client, public ACME and earlier partial security-scan limits are unchanged.

The second CI attempt cleared dependency audits and passed six native guest jobs, but both main jobs failed the private Nginx certificate-activation fixture (750 tests, one failure). It overwrote certificate/key bytes on the same inode within one timestamp tick; [Nginx can inherit SSL objects when file index and modification time are unchanged](https://nginx.org/en/docs/ngx_core_module.html#ssl_object_cache_inheritable). The fixture now atomically replaces its synthetic files to model ACME activation. The real issuance hook and Production Nginx are unchanged; the final full CI verifies this fixture correction.

The next CI attempt passed752 unit/governance tests (80 explicit platform/fixture skips),82 root fixtures,38 security regressions,37 router controls, the real isolated VPN handshake, build/lint and six native jobs. It then correctly stopped at the runtime npm audit: inherited follow-redirects1.16.0 is affected by three credential-stripping advisories, including [GHSA-mrwp-f3q8-3g9p](https://github.com/advisories/GHSA-mrwp-f3q8-3g9p). Only that transitive lock entry changed to1.16.2; local runtime audit now reports zero vulnerabilities. The final exact-source/browser results are recorded above; no audit threshold or assertion was relaxed.

Source08f5ba3 passed the complete push CI. The simultaneous PR validation reached browser tests and read the Users online card's initial0 before its asynchronous request rendered (the same source passed this case in push CI). The fixture now waits at most five seconds for the expected3 before reading and comparing counters; an incorrect final value still fails. No application UI or API behavior changed. The final exact-source runs listed above pass; a deliberate750ms users/presence response delay reproduced the old failure in all four EN/FA/mobile/desktop cases and the corrected fixture passed all four.

[English notes](RELEASE-NOTES-v1.0.62.md) · [یادداشت فارسی](RELEASE-NOTES-v1.0.62.fa.md) · [Incident](incidents/2026-10-31-native-backup-disk-growth.md)
