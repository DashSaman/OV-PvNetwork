# Updates and rollback

## Before updating

Run diagnostics and create an explicit backup when making production changes:

```bash
ovpv doctor
ovpv backup
```

If you use an external PostgreSQL database, keep a database-native backup as well; the application backup does not replace your PostgreSQL backup policy.

## Update to latest stable release

```bash
ovpv update
```

The manager resolves the latest published GitHub Release, creates a pre-update backup, downloads the tagged source, preserves runtime `.env` and data, applies migrations/builds, restarts only `ov-panel.service`, then verifies the local API. Failed verification triggers source/data restoration from the pre-update application backup.

## Target a specific release

```bash
OVPV_REF=v1.0.1 ovpv update
```

A branch name can also be supplied for testing, but production should normally use signed-off tagged releases.
## Rollback

Rollback to the most recent application backup:

```bash
ovpv rollback
```

Or select a backup directory explicitly:

```bash
ovpv rollback /var/backups/ov-pvnetwork/YYYYMMDD-HHMMSS
```

Rollback restores the captured application tree/runtime data, rebuilds dependencies/assets, restarts the panel and verifies health.

## Status and version

```bash
ovpv status
ovpv version
ovpv doctor
```

## Release rule

Every production-visible change should update `CHANGELOG.md` and ship through a new tagged GitHub Release. Do not point production installations at an arbitrary development branch unless you are deliberately testing it.
