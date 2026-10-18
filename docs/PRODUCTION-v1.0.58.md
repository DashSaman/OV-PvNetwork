# Authorized panel deployment v1.0.58 — PVN-1042

On 2026-10-18, the owner explicitly authorized deploying QA58 to the existing panel with recoverable backup/rollback readiness and testing its node-install form while preserving active services and customer state. The exact public archive was activated successfully. Supported Stable remains v1.0.37; QA58 is still a prerelease.

| Gate | Actual result |
| --- | --- |
| Frozen source | `2c6ee6e9b8894125659d87a4bfd99817870a0440` |
| Archive SHA256 | `cff93a239dac5f2b147a1397eb019af6473b68a26dc43d99cb6cc67f0b1d3a60` |
| Native backup and actual PostgreSQL restore rehearsal | PASS; 33 tables, 7 runtime files, 5 checksums; private backup copies/paths retained on the authorized host |
| Isolated restored candidate and health canary | PASS before switching live code |
| Code rollback readiness | Previous 55 release/environment/venv retained; schema `i1b2c3d4e5f6` compatible; backup reverified and installed rollback help checked |
| Local/public health, exact UI assets and authenticated APIs | PASS on 1.0.58 |
| Existing cached profile | PASS locally/publicly; CA, certificate, private-key identity and cached node file unchanged; no profile material retained in public evidence |
| Complete customer/admin/node/assignment identity snapshots | PASS; private full snapshot counts and hashes match before/after |
| Protected host state | VPN/foreign service MainPIDs, VPN configuration hashes, encryption-key identity, existing environment and final proxy configuration preserved |
| Sampled panel maintenance | 129.07 seconds observed unhealthy span; 125 samples; sampling is not a claim of continuous packet-level outage measurement |
| Subsequent continuity | Two public/API health samples, exact recovered memberships, stored-host SSH reconnect and protected target-node files/services PASS |

The native update journal retains its complete transaction and pinned final backup. A compatible code rollback keeps current live customer data; it does not restore an older database dump. Rollback readiness was checked after deployment; no unnecessary live rollback cycle was executed. No VPN/tunnel/node restart, node reinstallation, credential/certificate rotation or firewall/routing change was performed.

## Actual in-panel node form checks

A separate ephemeral authenticated browser loaded the real deployed interface in 4 cases: EN/dark 1440px, FA/light 390px, EN/light 768px and FA/dark 768px. The browser blocked every unexpected mutation request. Each permitted request used a reserved documentation address, synthetic credentials and SSH port 0; the real backend returned 422 with an `ssh_port` schema error before a deployment job handler could run. No SSH session, installation, adoption or customer mutation was attempted by these form tests. Short-lived maintenance auth stayed only in encrypted SSH/child stdin and ephemeral browser memory, never in repository, command arguments or reports.

The named native dialog, associated fingerprint help, error/log exposure, focus containment/exact return and secret clearing after HTTP rejection pass. These checks validate the actual form and backend rejection path. They do not prove a complete fresh-node install or external VPN connection. No empty VPS is available; busy nodes remain protected.

Visual review identified one inherited usability issue: structured 422 validation arrays display `[object Object]` rather than the field message. Source 55 has the same string conversion, so this is not a new 58 regression. Recovery remains usable and SSH secrets are cleared. `PVN-1044` queues its correction and structured-response regression for the next immutable patch; it is not labeled fixed or a readability pass. Raw live screenshots and evidence remain private.

## Remaining release limits

Actual assistive hardware/screen-reader/speech sessions, public ACME issuance/renewal, independent external fresh-node/client tests and the inherited structured-message correction remain open. The sealed source45 security assessment retains its explicit partial coverage. [QA evidence](VALIDATION-v1.0.58.md) · [English illustrated guide](MANUAL-ACCESSIBILITY-v1.0.58.md) · [راهنمای تصویری فارسی](MANUAL-ACCESSIBILITY-v1.0.58.fa.md).

فارسی: نسخهٔ 58 با مجوز صریح مالک و پس از بکاپ قابل‌بازیابی، canary و بررسی آمادگی rollback روی پنل مستقر شد. هویت کاربران و تخصیص‌ها، کلیدها، پیکربندی و پردازش‌های سرویس‌های نامرتبط حفظ شدند. وقفهٔ مشاهده‌شدهٔ پنل حدود ۱۲۹ ثانیه بود. فرم واقعی در چهار حالت بررسی شد و درخواست‌های پورت SSH نامعتبر پیش از ایجاد job رد شدند؛ فوکوس و پاک‌شدن رمز درست‌اند. نمایش عمومیِ `[object Object]` برای آرایهٔ خطای اعتبارسنجی، ایراد قدیمیِ باز است. نصب کامل نود خالی، اتصال کلاینت بیرونی و بررسی سخت‌افزار دسترس‌پذیری هنوز تأیید نشده‌اند؛ Stable v1.0.37 تغییر نکرده است.
