# Production snapshot workflow

The running OV-PvNetwork instance contains the authoritative result of many incremental production changes. Reconstructing those files from historical shell snippets risks dropping a small but important behavior. Stable 1:1 publication therefore uses a sanitized source export.

## Export

On the production panel server:

```bash
bash /usr/local/lib/ov-pvnetwork/current/scripts/export-production.sh
```

If the distribution has not yet been installed on that server, download the exporter directly from this repository and run it as root.

The exporter copies application source while excluding:

- `.env` and environment-secret files
- databases and runtime state
- virtual environments and `node_modules`
- logs and backups
- `.ovpn` profiles
- private keys, PEM/P12/PFX/CRT material
- downloaded MSI/APK/DMG client installers

It also writes SHA-256 metadata and a conservative secret-scan report.

## Review gate

Do **not** publish the archive if `secret-scan.txt` is non-empty until every finding has been reviewed. A clean scan is necessary but not sufficient: inspect deployment-specific URLs, usernames, chat IDs, IP addresses and branding assets before public release.

## Stable import

The reviewed source is then imported into a versioned `production/` or application tree, CI is run, and the installer manifest is changed from `release-candidate` to `stable`.
