# Updates and rollback

## Update

```bash
ovpv update
```

The manager creates a backup before applying distribution changes, rebuilds the frontend/backend environment and verifies the local API. A failed verification triggers restoration of the pre-update backup.

## Manual backup

```bash
ovpv backup
```

Backups are stored under `/var/backups/ov-pvnetwork/`.

## Rollback

```bash
ovpv rollback
```

or choose a specific directory:

```bash
ovpv rollback /var/backups/ov-pvnetwork/YYYYMMDD-HHMMSS
```

## Version channels

`OVPV_REF` can point the bootstrap at another branch while testing:

```bash
OVPV_REF=release-v1.0.0 bash <(curl -fsSL https://raw.githubusercontent.com/DashSaman/OV-PvNetwork/release-v1.0.0/install.sh)
```

Stable deployments should use a tagged release after the production snapshot has been audited.
