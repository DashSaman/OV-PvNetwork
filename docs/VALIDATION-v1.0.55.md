# v1.0.55 validation checkpoint — PVN-1039

## Scope and reproduced failure

The owner authorized continuing the limited panel update with short panel maintenance. The exact immutable v1.0.54 attempt stopped before activation: the native snapshot rejected changing `data/app.log` during the PostgreSQL backup. The existing application remained v1.0.40. Metadata inspection identified only that append-only diagnostic log as changing; credential/push keys and SSH trust were stable. No new VPN/node/firewall changes are part of this authorization.

The patch excludes exactly `data/app.log` from native restorable runtime/source snapshots. It leaves the live diagnostic log untouched. Unknown `.log` files, SSH trust and key bytes retain the original consistency/checksum checks. There is no UI or schema change in this patch.

## Executed checks

- Real Linux synthetic fixtures against the actual lifecycle engine: before the fix, active log writes reproduced `runtime keys/files changed during database snapshot`; after the fix, all three pass: active-log backup with actual SQLite restore, changed-key refusal and unclassified-log refusal. Fixture paths and database were isolated from the live installation.
- Initial source `cb911d1265b40be304925df1d871aedb1198e19b` CI [39034670476](https://github.com/DashSaman/OV-PvNetwork/actions/runs/39034670476) passed all four jobs, including actual native fresh/repeat on Ubuntu 22.04, Ubuntu 24.04 and Debian 12. Validation discovered 729 tests with 80 explicit skips; separate root gate ran 82 tests, security gate 38 and router gate 37 with one explicit SSH skip. All three new Linux regression tests ran and passed. Real dual-auth handshake passed; dependency audits reported no known vulnerabilities. Later documentation/version-pin changes require a fresh exact-head CI run before release.
- Local applicable metadata/brand/rename contracts: 18 pass. Native durable snapshot fixtures require Linux; Windows is not a substitute for those tests. Local frontend quiet lint and production build pass; largest JS chunk remains 987,783 bytes under the existing 990,000-byte gate.
- Documentation: both READMEs, English/Persian illustrated UI, installation, node, CLI and update/recovery guides refreshed. 80 synthetic current captures cover 20 views × EN/FA × desktop/phone. The actual browser capture scripts and real Jinja subscription template use synthetic fixtures, abort external HTTP requests and include no Production data. Contact sheets and representative full-resolution forms inspected. Local relative links/anchors, PNG integrity/widths, Markdown fences and explicit private-marker checks passed. Documentation screenshots do not certify backend workflows or the complete responsive/accessibility matrix.

## Remaining release gates

Final exact commit CI/artifact checksum, immutable QA publication and anonymous re-download, public bootstrap on the three supported distributions, fresh native PostgreSQL backup/restore rehearsal, exact canary and the authorized limited panel deployment/post-checks remain gates until results are recorded here. Do not infer Production activation from a GitHub merge or QA release.

Inherited evidence and limits are retained in [v1.0.54 validation](VALIDATION-v1.0.54.md). Public ACME issuance, ARM and a separate empty external VPS have not been fully validated in this mission. The original native security workbench remains partial/unsealed; five validated findings were fixed in v1.0.46/v1.0.50. No independent completed security certificate or formal FINAL/100% claim is made.

فارسی: خطای تغییر هم‌زمان لاگ روی Linux بازتولید و پس از اصلاح محدود، هر سه آزمون بکاپ/بازیابی و کنترل ثبات پاس شدند. مستندات دو‌زبانه و ۸۰ تصویر فقط Demo هستند. فعال‌سازی Production، انتشار پایدار و پایان کامل مأموریت تا ثبت gateهای باقی‌مانده اعلام نشده‌اند.
