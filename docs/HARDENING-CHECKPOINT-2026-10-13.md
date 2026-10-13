# Production hardening checkpoint — 2026-10-13

Status: **PARTIAL**. Three narrowly scoped fixes have been verified on the owner-authorized controller. The whole-product FINAL/public release gate remains **BLOCKED**. This document contains sanitized operational evidence; credentials, host addresses, domains, private paths and customer data remain in the owner's private audit.

## Verified changes

| Task | Candidate | Deployed commit | Exact-commit CI | Production outcome |
| --- | --- | --- | --- | --- |
| PVN-1023 | 1.0.38 | `256589921cde80caed819623f046f5fca0d76d0b` | [PASS](https://github.com/DashSaman/OV-PvNetwork/actions/runs/38386074970) | Dependency/build update; canary, public/local health, UI/assets and read-only API checks passed. |
| PVN-1022 | 1.0.39 | `d569bdcee9d8bedf13ddb2605760ddddde98e124` | [PASS](https://github.com/DashSaman/OV-PvNetwork/actions/runs/38386150273) | Migration-filter correction; official smoke executable and systemd oneshot passed against the unchanged database revision. |
| PVN-1024 | 1.0.40 | `7592fff59fa6f826a75ea400ae4b9ade89965af9` | [PASS](https://github.com/DashSaman/OV-PvNetwork/actions/runs/38386166653) | Bounded helper installed; normal timer invocation passed without repair. |

Every deployment was serial, followed a fresh application and native PostgreSQL backup, and verified an actual restore into a newly created temporary test database. Temporary restore databases were removed after successful validation. Canary lifespan scheduling was disabled, traffic passed canary checks before the canonical panel restarted, and the canonical proxy route was restored and verified before the canary stopped. Only the panel restarted once per candidate to load version metadata. No database migration, node/VPN restart, firewall or route change occurred.

Aggregate user/node counts and migration identity stayed equal to the baseline. The controller environment hash, protected service PIDs and OpenVPN configuration hashes stayed equal across each rollout. Post-deploy probes found all configured node APIs healthy. This establishes control-plane health and preservation checks; it does not prove a new remote VPN client's traffic, accounting or fresh node installation.

The final CI includes backend/governance/security tests, Bash/Python compilation, a real disposable OpenVPN dual-auth handshake, frontend lint/build/dependency audit and bundle budget, browser responsive tests, JSON validation and basic private-material guards. Local regression fixtures passed for the smoke revision filter (six cases) and healthcheck safety (eleven cases). Both full and production frontend audits reported zero vulnerabilities at the tested lockfile. Browser fixtures passed for Persian/English at nine widths and for quick edit, node selector, online truth, Router, settings, security and subscription flows. These fixtures are not fresh-production node bootstrap E2E.

## Retained diagnostics

An early Windows suite was unsuitable for POSIX integration: missing dependencies, executable permissions and operating-system APIs caused failures. Its original output remains in the private audit. A local Docker real-handshake attempt failed during a guest-clock jump; a subsequent isolated real handshake passed. Final exact-commit Linux CI is green; no clock/TLS bypass was introduced.

Two deployment harness preflights were corrected before their respective live switches: relative frontend asset URL resolution and Windows CRLF source-export hash normalization. The previous healthy version was verified after each aborted attempt. Canonical LF archives were used for the subsequent candidates. These were harness failures, not product defects.

## Open gates and next work

- **Installer (P0):** `install.sh` retrieves its source archive without validating a release checksum; `install-local.sh` downloads executable dependency setup scripts, binds the backend to loopback and can print a public URL without configuring a usable TLS/reverse-proxy path.
- **Lifecycle (P0):** `scripts/manage.sh` still applies `rsync --delete` before build/migration success and lacks a complete native external-database restore workflow and rollback for every earlier failure stage. The limited rollout deliberately used a separately verified serial canary procedure.
- **Node/runtime naming (P0):** the live local agent still uses historical runtime paths/service names. Any migration must preserve certificates, sessions, database identity and integrations; it was outside the limited deployment authorization.
- **Real installation and fleet E2E:** the owner has no empty VPS. Fresh Ubuntu 22.04/24.04 and Debian 12 installation, panel-only node bootstrap, remote-client traffic and accounting require a suitable isolated target. The existing busy hosts are not fresh-install test hosts.
- **CLI (P1):** deployed `version` and `status` are verified. This does not certify the full requested bilingual menu or every lifecycle command.
- **Host safety:** pre-existing failed host-hardening and unrelated tunnel units remain unresolved. Historical claims of key-only SSH do not establish the current host configuration. No host firewall, SSH or tunnel remediation was performed in this authorization.
- **Public release:** these are still candidates. Main/latest stable remain the previous release; draft PRs hold the candidate commits. Merge, immutable tags, release assets, download verification and the remaining privacy/documentation/fresh-install gates must precede stable publication. Do not instruct users to install these candidate tags as stable releases.

Resume from this checkpoint. Do not redo the three verified fixes. Continue the installer/lifecycle gaps in isolated branches, and keep Production changes within separately authorized scope.

## خلاصهٔ فارسی

سه اصلاح محدود وابستگی‌های فرانت‌اند، تشخیص revision در smoke test و ایمنی healthcheck با CI سبز، بکاپ تازه و بازیابی آزمایشی، به‌ترتیب روی کنترل‌پنل مجاز مستقر و تأیید شدند. نسخهٔ عملیاتی اکنون 1.0.40 است. کاربران و نودها، دیتابیس، تنظیمات VPN و سرویس‌های محافظت‌شده حفظ شدند؛ تایمر عادی healthcheck نیز موفق بود.

وضعیت کل مأموریت **PARTIAL** و انتشار نهایی **BLOCKED** است. نصب تازه و TLS، صحت بستهٔ Installer، بازیابی کامل Update/Rollback، مهاجرت امن نام‌گذاری نود قدیمی و تست واقعی نصب نود و ترافیک باقی مانده‌اند. سرور خالی برای تست مستقل در اختیار نیست. نسخه‌های آماده هنوز candidate هستند؛ انتشار عمومی نهایی اعلام نشده است.
