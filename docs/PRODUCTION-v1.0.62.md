# v1.0.62 — verified operational scope (PVN-1047)

The owner authorized diagnosis, scoped cleanup and recurrence prevention while preserving active services and customer data. Only the native lifecycle helper was activated; the application remains1.0.60. This is not a full61/62 rollout or Stable promotion.

## Frozen source and scope

- Source: `cd305783f4b0836bb0f1416a004ca55ddbe5b607`; [merged PR86](https://github.com/DashSaman/OV-PvNetwork/pull/86) retained the exact tested source tree.
- [Immutable QA62](https://github.com/DashSaman/OV-PvNetwork/releases/tag/v1.0.62), archive SHA256 `f3605e6b9069be9dad698f3ce9cb950de1f1b6a65842ee08d2ac738e3a277223`.
- Installed helper SHA256 `e13eb6655102297e25053b48c0e9992c3842c0c55e8c0fef91de88f6f256abc3` in its two existing script locations. No schema, frontend, environment, keys, node configuration, firewall or route activation.

## Backup, activation and actual checks

A fresh native snapshot completed a real PostgreSQL restore of33 tables and five checksum checks before activation. Two verified original module copies and a root-private rollback utility were ready before the atomic replacements, under the native operation lock. The rollback utility's check passed after activation; no database restore or service restart is needed to reverse the helper files.

The actual installed command used by the daily timer made another backup and restored/verified33 tables/five checksums. Its ten-day retention removed one newly eligible unreferenced expired checkpoint. The installed operational CLI then made and restored/verified another backup; repeat maintenance removed nothing further. Both maintenance receipts had zero warnings and no unrecovered rehearsal allocation. This verifies the real entrypoints, beyond mocked/unit coverage.

Complete customer identity/quota/assignment snapshots, protected service PIDs/restart counters and environment/key/VPN configuration hashes matched. Local and public health passed. The final independent check found zero backup-rehearsal databases and confirmed rollback readiness again. No live customer rows were deleted and no panel, VPN or foreign service restarted.

## Scoped storage recovery

After the earlier recoverable backup, four exact durably journal-owned, zero-connection disposable rehearsals and fourteen expired verified backups were removed. Eight proven unused reconstructible dependency caches were retired after process/unit-reference and path/inode checks. Current/rollback releases, pins, source archives, referenced caches and private evidence survived. These operations freed about7GB; the final panel-host reading was73% used, with about10.58GB available after the new verification backups (initially89%).

On a peer, two closed rotated log archives were compressed without discarding content. Decoded hashes matched their originals, the logrotate state lock excluded concurrent rotation, protected service state matched, and about0.69GB was freed. An actual logrotate fixture using disposable logs confirmed that the compressed generation stays in the existing rotation policy. No live log was truncated and no journald/service configuration was changed.

## Limits and follow-up

Another peer had no storage-pressure finding and needed no cleanup. One node's SSH port timed out from the workstation and three authorized servers; its owner currently has no provider console. Its disk has not been inspected or changed, and an administrative active flag is not proof of VPN-client connectivity.

The helper-only activation does not update the running application's dependency environment. Broader external-client, public ACME, assistive hardware and partial security-scan limits remain. Supported Stable stays1.0.37. Private paths, backup identifiers, database copies, credentials, host addresses and customer evidence remain outside the public repository.

[Validation](VALIDATION-v1.0.62.md) · [English changes](RELEASE-NOTES-v1.0.62.md) · [تغییرات فارسی](RELEASE-NOTES-v1.0.62.fa.md)
