# PVNetwork Panel v1.0.9 — سازگاری OpenVPN برای Router / MikroTik

PVN-029 یک مسیر **اختیاری و کاملاً جدا** برای RouterOS و دستگاه‌هایی اضافه می‌کند که Username/Password می‌خواهند. Listener و Profile عادی OpenVPN همچنان Certificate-Only باقی می‌مانند و برای کاربران معمولی هیچ Username/Password جدیدی لازم نیست.

## امکانات جدید

- Listener دوم برای هر Node با Port، Protocol، Subnet، Status file، Ruleهای Firewall و Rollback مستقل.
- احراز هویت هم‌زمان Certificate + Password؛ Common Name گواهی همچنان هویت اصلی User در PVNetwork است.
- Username/Password جدا برای هر User/Node؛ Password خام فقط موقع Generate/Rotate یک‌بار برگردانده می‌شود و در مرکز ذخیره نمی‌شود.
- Profile مخصوص Router و Command آماده Import برای RouterOS.
- Node قدیمی به‌صورت امن `upgrade_required` می‌دهد و OpenVPN معمولی را خراب نمی‌کند.
- Sessionهای Listener دوم با Common Name وارد Presence نمایشی می‌شوند، بدون Double Count و بدون ساخت Session اجرایی مصنوعی در `active_sessions`.
- تست UI فارسی/انگلیسی روی موبایل/دسکتاپ و تست واقعی Handshake ایزوله OpenVPN.

## مرزهای ایمنی

- `server.conf`، PID/Config سرویس اصلی OpenVPN، Template عادی و Profileهای موجود توسط این قابلیت بازنویسی نمی‌شوند.
- کاربران معمولی Credential روتر دریافت نمی‌کنند و به آن نیاز ندارند.
- Enable/Disable کردن Router Compatibility سرویس `openvpn-server@server` را Restart نمی‌کند.
- برخورد Port/Subnet قبل از Mutation رد می‌شود و خطای Listener دوم فقط State همان Listener را Rollback می‌کند.
- Disable/Delete کاربر یا حذف Assignment، Credential مربوط به Router را بعد از تصمیم قطعی User/Assignment به‌صورت Best-Effort غیرفعال/Revoke می‌کند.

![جریان کاربر Router](./images/v1.0.9/fa/desktop/router-user.png)

![جریان Node Router](./images/v1.0.9/fa/mobile/router-node.png)
