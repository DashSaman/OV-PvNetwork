# PVNetwork final completion plan

Resume from verified Production candidate 1.0.40 and documentation checkpoint `2e49d22`. Do not repeat PVN-1022/1023/1024. The owner requests autonomous implementation/testing of all achievable remaining gates; Production changes beyond the prior three patches, especially node downtime, firewall or SSH changes, need separate concrete authorization.

## Architecture and decisions

Reuse the existing FastAPI/React application, unit names, DB models, SSH trust helper and browser fixtures. Replace the unsafe installation/lifecycle orchestration, not working product features. Release contents are built in a stable immutable release directory; `/opt/pvnetwork-panel` resolves to the selected release. Runtime environment/data stay in a separately protected shared directory. A shared operation lock and durable transaction journal cover install/update/restore/rollback. Failed builds must not touch the active tree. Native dumps and real isolated restores establish backup validity. Migration changes require a database recovery path and controlled writer pause. Canary lifespan is disabled to prevent duplicate schedulers. Preserve the existing rooted installation with an explicit migration path instead of silently replacing it.

Bootstrap accepts only sequential immutable release versions and downloads the official source asset plus checksum. Validate hash, archive paths/types and release metadata before execution. Pin toolchain and project locks; never pipe third-party setup scripts to a shell. Install private tools without replacing unrelated host Node/Python versions. Fresh setup defaults to loopback access through SSH forwarding; public HTTPS requires a validated domain and successful ACME/proxy checks. No unusable public URL is announced as verified.

Node preflight must distinguish fresh installation from intentional adoption and reject listener conflicts before mutation. Reuse the existing fingerprint approval helper. A PVNetwork-owned agent/build must have verified provenance and preserve third-party attribution. Existing node migration remains opt-in and may not restart live OpenVPN merely for naming.

## Sequential tasks / release reservations

1. **PVN-1025 / 1.0.41: verified installer and public defaults.** Write executable regressions for corrupt/wrong-version/path-traversal archives, unsupported hosts, occupied ports, existing install and truthful URL reporting. Implement verified bootstrap, pinned private toolchain, fresh setup/recovery and generic smoke fallback. Test real supported distribution containers; label systemd/TLS/public-network coverage precisely.
2. **PVN-1026 / 1.0.42: lifecycle transaction safety.** Reuse native backup/restore code where safe. Cover SQLite online backup and PostgreSQL dump/restore, checksums, shared lock, stage build/migration clone, canary, pointer switch and durable recovery. Inject failures before/after activation and process interruption; verify data/env/source/service state after rollback. Preserve old rooted installs through an explicit conversion step.
3. **PVN-1027 / 1.0.43: node provenance and adoption.** Map current agent APIs/PKI/accounting, add checksum/provenance and early host/port checks, then provide PVNetwork paths and safe migration/adoption. Tests prove existing OpenVPN configs and sessions are not gratuitously restarted.
4. **PVN-1028 / 1.0.44: complete panel node deployment.** Separate fresh/adopt workflows; ensure registration and remote success are recoverable on later controller errors. Cover real SSH, host key, installed agent, health and disposable OpenVPN handshake/traffic/accounting in an isolated environment.
5. **PVN-1029 / 1.0.45: CLI.** Add bilingual lightweight menu over tested operations, read-only doctor, scoped repair, JSON/help/dry-run/confirmations and sanitized support bundle. Do not invent PASS for unsupported operations.
6. **Final regression/documentation/privacy/publication.** Preserve 13 languages, run appropriate API/UI/security suites, create demo-only screenshots/guides, scan tracked source/history/build/archive/images, record exposures privately without rewriting published tags, consolidate stacked PRs in dependency order, run final exact-commit CI. Publish immutable sequential releases/assets only when applicable gates pass and download verification succeeds.

## Test boundaries

Local Docker is available. Container builds/tests are real for package installation, application, database and process operations that actually run. A mocked systemctl test is a contract test, not real boot verification. Only record real TUN/systemd/TLS/external-client PASS when actually exercised. Do not change operational host ports, routes, firewall, containers or services to create a test environment. Keep the busy shared server read-only. Lack of an empty VPS does not block implementation or supported local tests.

## Checkpoint discipline

Commit each task's reservation, red/green evidence and final scope. Keep active tasks `[~]` until tests, authorized deployment where applicable, publication and artifact download checks all pass. Every remaining gate receives PASS/FAIL/NOT TESTED evidence. Never label the whole product FINAL with open P0 or mandatory untested gates.
