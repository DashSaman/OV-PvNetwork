# Verified update, rollback and recovery

[فارسی](UPDATES.fa.md) · [Installation](INSTALLATION.md) · [CLI](CLI.md)

## 1. Prepare a reviewed update

1. Read the target release's status, changes and migration/rollback limits. A QA prerelease is not the supported stable release. Select an immutable published tag; a branch is not a native update source.
2. Run read-only `sudo pvnetwork status --json`, `doctor --json`, `database check --json` and `jobs --json`. Resolve an unfinished owned transaction before starting another mutation.
3. Run `sudo pvnetwork backup --json`. Retain the returned verified path, private application/runtime archive and database-native snapshot. Native verification includes an actual restore rehearsal and checksums. A failed backup directory is not a rollback point.
4. Check free disk, the retained previous release, compatible schema and node transports. Schedule the required short panel maintenance; preserve unrelated VPNs, routes, firewall and services.

## 2. Update an eligible installation

After its official assets exist and gates have passed, an explicitly selected QA update is:

```bash
sudo pvnetwork update v1.0.56 --dry-run --json
sudo pvnetwork update v1.0.56 --yes --json
```

On an eligible older rooted installation, `--adopt-rooted` is an explicit, separate opt-in; inspect `pvnetwork update --help` and rehearse the verified path before using it. Do not replace the active directory manually.

The engine verifies the immutable checksum/version, creates a native backup, builds a staged release, restores an isolated database clone, checks the allowed migration and authenticates canary health. It then enters panel maintenance, pauses owned writers, takes the final quiesced backup, performs the permitted migration, switches the pointer and verifies health. It restarts only the required panel service and gracefully reloads the managed proxy; unrelated VPN services remain outside this scope.

## 3. Verify after activation

1. Confirm version, active service, local/public HTTPS health and actual current UI assets.
2. Check user/admin/node identities and assignments, configuration/key preservation and database readability.
3. Test the changed workflow: for example the default/selected profile download. Use a synthetic test identity for mutating probes.
4. Inspect post-deploy errors and job state. Confirm unrelated service health/PIDs and VPN traffic remain intact.
5. Record exact commit, checksum, verified backup path, restart/maintenance observations and rollback readiness privately; publish only sanitized evidence.

## 4. Distinguish code rollback from data restore

`sudo pvnetwork rollback --yes --json` selects the retained previous completed native update. It requires schema and node-transport compatibility, switches application code and retains compatible **current live data**. It does not accept an arbitrary backup-directory argument.

`sudo pvnetwork restore BACKUP_ID --yes --json` is an explicit native data restore using a verified backup ID. It has different data-loss/maintenance consequences; inspect the selected backup and supported restore scope first. Web-upload restore uses its matching archive format and job flow. Do not replay an old database dump after users have made new changes merely to undo application code.

For interrupted update/settings/data operations, inspect `sudo pvnetwork jobs --json`, then use `sudo pvnetwork recover --yes --json` for the matching owned journal. An unfinished operation uses recovery rather than pretending a completed-update rollback exists. Read its terminal result and verify health before another update.

## 5. Snapshot boundaries

Native v1.0.55 omits only the panel's append-only diagnostic `data/app.log` from runtime/source snapshots; it leaves the original log untouched. Unknown `.log` files, key bytes and SSH trust remain checked. Credential/push keys, `.env`, database and supported runtime files are private backup contents and must not be uploaded to public GitHub issues.

[Illustrated backup guide](UI-GUIDE.md#11-panel-backup-and-restore) · [Release evidence](VALIDATION-v1.0.54.md)
