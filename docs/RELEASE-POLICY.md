# Release Policy

PVNetwork Panel uses semantic versioning and treats the live production service as a deployment target, not as the development workspace.

## Versioning

- `1.0.x`: backward-compatible bug and security fixes.
- `1.x.0`: backward-compatible features.
- `2.0.0`: breaking architecture, configuration, API or protocol changes.

## Stable release gate

A stable release is published only after:

1. Python compilation succeeds.
2. Targeted regression tests pass.
3. Frontend production build succeeds without a production `.env`.
4. The public source tree contains no production credentials, hostnames/IPs, databases, customer data, VPN profiles, private keys or certificates.
5. Secret-scan findings are reviewed.
6. The release archive is hashed with SHA-256.
7. Install/update documentation matches the released artifact.

## Production deployment rule

Before deploying an update to a live instance, create a backup and verify database migration compatibility. Restart only services required by that update and run local HTTP/service health checks immediately after deployment. Roll back if verification fails.

## v1.0.0 freeze

The `v1.0.0` tag and every published patch tag are immutable. Each new Production-visible `PVN-xxx` task advances exactly one patch version (`v1.0.1`, `v1.0.2`, `v1.0.3`, ...), unless the human owner explicitly changes the versioning rule. New behavior must never be silently added to an existing tag or release asset.
