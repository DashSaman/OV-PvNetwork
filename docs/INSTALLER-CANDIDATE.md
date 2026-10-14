# Verified installer candidate — PVN-1025

Status: implementation under validation; not a published stable release. The versioned bootstrap must not be advertised as a tested public installation command until its official assets exist and download verification and release gates pass.

## Fresh installation contract

Supported host checks: Ubuntu 22.04/24.04 and Debian 12, x86_64/aarch64, at least 1 GiB RAM and 3 GiB free disk. Only the architectures actually exercised receive installation PASS. Occupied panel/setup ports, an existing installation, existing panel units/site or nonempty database are refused. A repeat of the exact completed release verifies health and returns without rebuilding or changing credentials. A same-version source hash change is refused.

The bootstrap downloads `pvnetwork-panel-vVERSION.tar.gz` and its `.sha256` from the official immutable GitHub Release, validates SHA256, archive types/paths/duplicates/size and matching VERSION/manifest/frontend metadata, then runs `install-local.sh`. Branch sources are refused. Private pinned tools are installed under `/opt/pvnetwork-panel-tools` without replacing unrelated host Python/Node. Pins and upstream hashes are in `ops/toolchain.json`. Project dependencies use `uv sync --frozen --no-dev`; frontend uses `npm ci`. OS packages come from signed native repositories. An optional `PVNETWORK_TOOL_CACHE` accepts only matching pinned files and rejects corrupt offline cache content.

The application is built in `/opt/pvnetwork-panel-releases/vVERSION-ID`; `/opt/pvnetwork-panel` becomes an atomic symlink only after build and database initialization. Runtime `.env` and data live in `/var/lib/pvnetwork-panel/runtime` with restrictive permissions. Initial credentials are in `/etc/pvnetwork-panel/initial-credentials.txt`, mode 600, never emitted into install logs. Existing data uses a distinct upgrade/adoption path, not fresh installation.

## Access modes

Default Setup Mode runs the backend on loopback and an owned Nginx server on `127.0.0.1:18443`. The reported address is `http://127.0.0.1:18443/panel/`, used through encrypted SSH forwarding: `ssh -L 18443:127.0.0.1:18443 USER@SERVER`. It is explicitly not a public URL. Configure a public domain later through a separately verified settings/TLS operation.

For a fresh HTTPS target, pass `--domain panel.example.com --email operator@example.com`. Ports 80/443 must be free, DNS must resolve and inbound ACME validation must be possible. Until a certificate is issued, the HTTP server serves ACME challenges and returns 503 for other requests. The installer validates Nginx configuration, verifies local backend health, obtains a certificate via Certbot, switches to HTTPS, validates public TLS/health/UI and enables renewal. It does not change firewall rules to make ACME succeed. Failed issuance does not announce a usable public HTTPS URL. Do not use `.example` values as real public targets.

## Database and recovery

Empty databases use the canonical current models, including device/session constraints, and stamp the single current head. SQLite construction occurs in an isolated file and switches atomically after integrity checks. PostgreSQL construction and the head stamp share one transactional DDL operation; injected failure leaves no tables. Historical migrations are unchanged and remain the upgrade path for existing databases. External databases must be dedicated and empty for fresh installation; existing schemas are refused.

A shared operation lock and root-only `/etc/pvnetwork-panel/install-transaction.json` journal track staging, tools, build, database, activation, health and timers. `--recover` resumes a matching interrupted/failed release after restoring only its owned files/pointer/services. Runtime secrets/data are retained. A completion marker identifies an owned fresh database if interruption occurs between initialization and journal commit. A failed fresh install is not permission to erase an existing deployment or database.

## Evidence and limitations

Executable Linux tests reproduced the old bootstrap accepting a bad checksum, wrong version and symlink archive. Additional tests cover resource/OS/architecture/port checks, existing-data refusal, constrained fresh SQLite, atomic schema failure, secure pre-TLS configuration and recoverable journal phases. Real disposable systemd distribution containers are used for package/build/service/proxy/database checks; contract fixtures are labelled separately.

Real fresh-install tests exposed historical migrations that assume tables from old runtime bootstrap code, on both SQLite and PostgreSQL. Diagnostics are retained privately; the empty-schema bootstrap fixes this path without changing existing migrations/data. Real PostgreSQL tests verify all current tables/head, existing-schema refusal and transaction rollback after injected failure. Public ACME, Internet reachability, final architecture matrix, native lifecycle recovery and node traffic are separate gates. This document does not claim those unexecuted gates have passed. Do not run fresh installation on a busy shared host.

Tooling safety backport: official Node archives now use bounded private staging, reject duplicate/traversal/linked-parent members and publish atomically into an absent tool directory. Timeout partial output stays in private 0600 diagnostics; errors omit sensitive arguments. Health verification accepts HTTPS or owned loopback HTTP only. The installer static gate now runs in CI. A reproduced missing SecuritySettings import in backup retention is corrected with an executable runtime regression. Final exact commit CI and distribution installation remain required.

Fresh source-only local Linux snapshot: 416 tests, 413 passes and three PostgreSQL-only skips; installer/backend medium/high static checks pass. The QA snapshot excludes files left in its base image.
