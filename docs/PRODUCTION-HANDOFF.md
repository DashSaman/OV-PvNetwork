# Production Handoff (Public-Safe)

This document intentionally contains no production IP addresses, domains, credentials, customer identifiers, node IDs, live user counts, private routes, or deployment-specific secrets.

## Public repository rule

The public repository must contain only reusable product behavior and generic operational guidance. Production-only values belong in environment variables, deployment state, private backups, or an internal operations repository.

Never commit:
- `.env` files or generated credentials
- API keys, JWT secrets, passwords, private keys, certificates, or VPN profiles
- production IP addresses, hostnames, domains, node identifiers, user/customer data, traffic totals, or live fleet counts
- database files, logs, backups, or support bundles containing real infrastructure data

## Safe production principles

- Back up the exact files or state affected before any mutation.
- Never flush the complete firewall or replace the default route blindly.
- Preserve unrelated services and existing NAT/tunnel rules on shared nodes.
- Node management APIs should be restricted to trusted management sources.
- Health/metrics enrichment must fail safely and must not make the core health endpoint unavailable.
- Profile generation should validate existing material first and avoid unnecessary certificate rotation.
- User renewal should preserve identity, assigned nodes, subscription identity, and existing optional service credentials.
- Database migrations, frontend builds, Python compilation, service health, and HTTP health checks must pass before a release is declared stable.

## OpenVPN node compatibility

PVNetwork supports compatibility handling for upstream OpenVPN/OV-Node template differences and validates generated client profiles before serving them. Endpoint values are always supplied from deployment configuration and must never be hard-coded in the public distribution.

## Metrics

Nodes may return raw cumulative interface counters while the dashboard derives live rates from sample deltas. Interface selection should prefer the system default-route interface and ignore obvious loopback/tunnel/container interfaces when calculating WAN rates.

## Release discipline

Every stable release should include:
- versioned release notes and changelog
- tested install/update/rollback paths
- migration verification
- public-source secret/identifier scan
- checksums for distributed artifacts
- no production-specific data

Private operational notes must be maintained outside this public repository.
