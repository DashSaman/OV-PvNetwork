# Authorized panel deployment v1.0.59 — PVN-1044

Since QA58, structured node-install validation is readable in both automatic SSH and manual registration. On 2026-10-19, the owner-authorized panel activated the exact public QA59 archive after fresh recoverable backup and rollback readiness. Supported Stable remains v1.0.37.

| Gate | Actual result |
| --- | --- |
| Frozen source | `c7b06307633b4b95ca52b3d6ddfc60884c6693c6` |
| Archive SHA256 | `91d79ab5fd35b34d659785f7af534f4ec027d40bcc5a7914db96e1216875f4e0` |
| Source/tag CI and anonymous download | PASS; unchanged immutable QA archive 90024153 bytes |
| Official public bootstrap | All six x86_64/real ARM64 Ubuntu22.04/24.04/Debian12 fresh/repeat guests PASS |
| Fresh native backup and actual PostgreSQL restore | PASS; 33 tables, 7 runtime files, 5 checksums; paths/copies retained privately |
| Before-activation rollback check | Existing 58 release/environment/venv present; candidate migration files identical; installed rollback help PASS |
| Exact candidate clone/canary | PASS before live switch; schema unchanged |
| Local/public health, exact UI assets and authenticated APIs | PASS on 1.0.59 |
| Existing cached assigned profile | Local/public PASS; CA/certificate/key identity and node cache preserved |
| Customer/admin/node/assignment state | Complete identity snapshots match before/after; private counts/hashes retained |
| Protected services and files | VPN/foreign MainPIDs, existing environment, encryption-key identity, VPN configuration and final proxy configuration preserved |
| Sampled panel maintenance | 136.78 seconds observed; sampling is not a packet-level continuity measurement |
| Post-activation continuity | No fresh traceback/5xx; two node/API/public-health samples and stored-known-host SSH PASS |
| Retained rollback | Previous 58 environment/venv/schema compatible, backup reverified and installed rollback help PASS; post-success readiness checked without another rollback |

The durable native transaction and verified final backup are retained on the authorized host. Compatible code rollback preserves current customer data. No node/VPN/tunnel restart, reinstallation, credential/certificate rotation or firewall/routing change was performed.

## Initial protective rollback and fresh attempt

The initial activation automatically returned to 58 when its strict foreign-service PID gate detected that two independently managed temporary units had ended during build, before panel maintenance. Complete customer identity snapshots and persistent critical VPN/foreign service PIDs, key/configuration and environment were verified after rollback; public/local58 health and the node API passed. The original transaction and failure journal are retained privately. Its sampled maintenance span was 131.89 seconds; the rollback's separate brief restart is not included in that sample window.

A read-only 25-second comparison found 39 stable running services. A subsequent precondition refused to start another panel mutation while other transient work remained active. After that independent work ended, a new journal/unit, fresh preflight and native backup preceded the successful second activation. Every original PID comparison remained enforced; no foreign process/timer was stopped, restarted or disabled to satisfy the gate. The successful attempt's sampled span is listed above. Compatible code rollback retained current customer data throughout.

فارسی: تلاش اول با تشخیص پایان دو واحد گذرای خارجی، خودکار به58 برگشت؛ هویت کاربران، کلیدها و سرویس‌های اصلی حفظ شدند. وقفهٔ مشاهده‌شدهٔ آن تلاش 131.89 ثانیه بود و restart کوتاه rollback جدا از این نمونه‌برداری است. پس از پایان فعالیت گذرای مستقل، تلاش دوم با ژورنال و بکاپ تازه و همان gate سخت‌گیرانه موفق شد.

## Actual changed workflow

Four ephemeral authenticated browser cases loaded the deployed UI: EN/dark 1440, FA/light 390, EN/light 768 and FA/dark 768. Each allowed only a reserved-address request with synthetic credentials and SSH port 0. The real backend returned 422 before any job/SSH handler; every unexpected mutation was blocked. The alert/log now contain the actual port message and translated field label, with no `[object Object]` or submitted secret. Native dialog naming, fingerprint help, focus containment/exact return and cleared SSH secrets PASS. Maintenance authentication stayed in encrypted SSH/child stdin and ephemeral browser memory; raw live images stay private.

The form test did not attempt a complete fresh-node installation or an external VPN connection. No empty VPS is available. Busy nodes remain protected. Actual assistive hardware/speech, public ACME, independent external node/client lifecycle and the sealed source 45 scan's partial-coverage limits remain recorded.

فارسی: نسخهٔ59 با مجوز مالک، بکاپ تازه و بازیابی واقعی، canary و آمادگی rollback مستقر شد. خطای پورت نامعتبر در چهار حالت واقعی، نام فیلد و پیام خوانا دارد و رمز پاک می‌شود؛ هیچ job نصب، SSH یا تغییر کاربر در این تست ساخته نشد. هویت کاربران و تخصیص‌ها، کلیدها، تنظیمات و پردازش‌های محافظت‌شده حفظ شدند. بازهٔ نگهداری مشاهده‌شدهٔ پنل 136.78 ثانیه بود؛ نصب نود خالی و اتصال VPN بیرونی هنوز آزموده نشده‌اند و Stable 37 تغییر نکرده است.

[Validation](VALIDATION-v1.0.59.md) · [English illustrated guide](NODE-VALIDATION-v1.0.59.md) · [راهنمای فارسی](NODE-VALIDATION-v1.0.59.fa.md)

## Inherited subscription follow-up

[PVN-1045](incidents/2026-10-19-subscription-template-contract.md) records three pre59 subscription 500 errors and the unchanged positional TemplateResponse contract. It remains queued for a new immutable patch; current 59 zero-error observation is limited to its candidate window and tested workflows. Historical private logs are retained.
