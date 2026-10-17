# v1.0.56 validation — PVN-1040

Status: **verified public QA; no new Production deployment**. Supported public Stable remains v1.0.37. The authorized live panel remains v1.0.55; this task did not renew a live certificate or change a service, database, node, firewall or route.

## Immutable artifact and CI

- Source `490af88fdc86b9306300620b5d2c8ba281186410`; [PR74](https://github.com/DashSaman/OV-PvNetwork/pull/74) merged as `a7d6ef24e86e854725e78f2b37ab161907f8906f` with an identical tree.
- [QA release](https://github.com/DashSaman/OV-PvNetwork/releases/tag/v1.0.56), SHA256 `de35e0f198c05a608097137f08977f1474e09f457a5618e26c0f6f0c49c49e65`. Both official assets were anonymously re-downloaded and verified;89,221,404 compressed bytes,93,959,317 expanded bytes,1,033 members. Tag/assets were not replaced. The public latest supported release remains v1.0.37.
- Exact [push CI39040481367](https://github.com/DashSaman/OV-PvNetwork/actions/runs/39040481367) and [PR CI39040484922](https://github.com/DashSaman/OV-PvNetwork/actions/runs/39040484922): all4 jobs PASS.733 discovered tests/80 explicit skips, separate82 root fixtures,38 security and37 router tests/one explicit SSH skip. Dependency audits, real dual-auth OpenVPN handshake, lint/build, browser/private-material guards pass. Largest JS987,783 bytes remains within990,000. Skips are not counted as passes.
- [Public x86 bootstrap39041339822](https://github.com/DashSaman/OV-PvNetwork/actions/runs/39041339822) and [real ARM64 bootstrap39041345019](https://github.com/DashSaman/OV-PvNetwork/actions/runs/39041345019): all6 distribution guests PASS, Ubuntu22.04/24.04 and Debian12 on each architecture. They verify the exact public artifact/bootstrap bytes, fresh install, preserving repeat, systemd/proxy/UI assets/SQLite/private permissions and installed CLI. ARM checks both aarch64 runner and arm64 guest. Only the disposable test base-image mapping differs from the pinned source harness.

## Reproduced defect and fix

The actual fresh HTTPS issuance command lacked a persistent Certbot deploy hook. A regression failed before the fix. Newly issued installer-managed lineages now store `nginx -t && systemctl reload nginx.service`; invalid syntax prevents reload. No restart, forced issuance or global hook-directory change was added. The original initial TLS/public-health gate remains.

All4 TLS fixtures execute in each of the6 public native guests: command persistence, successful hook, failed syntax-check refusal and real private Nginx TLS activation. Two synthetic certificates demonstrate that file replacement alone leaves the previous certificate served; invalid config does not reload; corrected config plus the actual hook serves the new certificate with the same master PID. The wrapper substitutes only the private configuration/master at the command boundary. It does not operate the guest panel's service. Private synthetic PKI and the random loopback listener are cleaned up.

Initial fixture failures came from executing wrappers on the guest's noexec `/tmp`. The corrected harness uses root-private temporary storage inside the disposable guest and retains the noexec mount. No service/security policy was weakened. Windows local check:16 passes/3 explicit Linux-only skips; Linux native jobs actually execute all4 new checks.

## Preservation, documentation and limits

Fresh read-only Production check at `2026-10-17T14:36:03Z`: local/public200/version1.0.55, panel/VPN/node/PostgreSQL active with the same protected PIDs, identity counts and environment/VPN configuration hashes; no recent traceback or5xx lines. No Production write or restart occurred in this continuation. The earlier authorized55 deployment's measured maintenance remains recorded in [its evidence](VALIDATION-v1.0.55.md).

Both READMEs, installation, update and CLI guides point to the verified QA56 assets and retain the supported Stable distinction. English/Persian release notes explain scope and upgrade limits.80 synthetic current UI images remain applicable because this patch changes no UI. Existing certificate lineages are not retrofitted by code update; review their automatic renewal separately in an authorized maintenance scope. Do not run fresh install over an existing panel.

| Remaining gate | Actual state / resource needed |
|---|---|
| Real public ACME issuance/renewal | NOT TESTED. Requires an authorized test domain with controlled DNS and an eligible empty host with reachable80/443. The synthetic TLS test is not a public-CA test. |
| Independent external VPS node/network lifecycle | NOT TESTED to completion. Requires a separate disposable owned node and authorized external client path. Busy live hosts are not fresh targets. |
| Original source45 security workbench | COMPLETED and sealed on 2026-10-17; canonical contract independently validates. Coverage remains PARTIAL, with five findings fixed in46/50. [Closure, test mapping and limits](SECURITY-SCAN-CLOSURE.md). No independent security certificate claimed. |
| Full accessibility certification | Broad screen-reader/icon/typography/WCAG/pixel-baseline audits remain explicitly deferred; scoped core browser/contrast/keyboard evidence is retained. |

فارسی: نسخه۱.۰.۵۶ به‌صورت QA عمومی با آرشیو ثابت بررسی شد. نصب عمومی هر سه توزیع روی x86_64 و ARM64 واقعی، تست گواهی ساختگی Nginx و CI دقیق موفق‌اند. پنل زنده۱.۰.۵۵ و سرویس‌های فعال حفظ شدند. اسکن قبلی رسماً تکمیل و مهر نهایی شده، با پوشش partial و پنج یافته اصلاح‌شده. صدور عمومی ACME و شبکه VPS مستقل هنوز تکمیل نشده‌اند؛ این گزارش اعلام Stable یا پایان صددرصد مأموریت نیست.
