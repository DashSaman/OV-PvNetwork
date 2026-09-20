# PVNetwork Panel v1.0.12 — PVN-032

در PVN-032 تغییر مسیر پنل و نام کاربری/رمز عبور مدیر اصلی از داخل صفحه Security Settings به‌صورت کنترل‌شده اضافه شده است.

## امنیت مدیر اصلی
- برای هر تغییر، رمز عبور فعلی مدیر اصلی دوباره بررسی می‌شود.
- رمز جدید فقط به‌صورت Hash یک‌طرفه موجود ذخیره می‌شود؛ Password خام وارد Job State، Log یا Artifact عمومی نمی‌شود.
- JWT مدیر اصلی دارای `MAIN_ADMIN_AUTH_GENERATION` است؛ با تغییر موفق Username/Password این Generation عوض می‌شود تا JWTهای قبلی مدیر اصلی معتبر نمانند.
- مرورگری که تغییر را آغاز کرده Replacement Token را موقت نگه می‌دارد و فقط بعد از `complete` شدن Job آن را فعال می‌کند.
- در تغییر Username، تنظیمات TOTP مدیر اصلی همراه حساب منتقل می‌شود و در Rollback به نام قبلی برمی‌گردد.

## تغییر مسیر پنل
- Frontend کاندید با Path جدید ساخته می‌شود و Panel کاندید ابتدا روی `127.0.0.1:19002` بررسی می‌شود.
- فقط بعد از موفقیت Canary، فایل Environment و Frontend Distribution به‌صورت Atomic سوییچ می‌شوند.
- اگر Verification نسخه اصلی بعد از سوییچ شکست بخورد، Environment و Frontend قبلی دقیقاً Restore می‌شوند و فقط سرویس پنل Restart می‌شود.
- Path قبلی دقیقاً **300 ثانیه** با HTTP **307** به همان Suffix روی Path جدید Redirect می‌شود و بعد از آن 404 عادی می‌دهد.

## ایزوله‌بودن VPN و Node
- PVN-032 فقط اجازه Restart کردن `pvnetwork-panel.service` را دارد.
- OpenVPN عادی، Listener اختیاری Router/MikroTik، سرویس `ov-node.service`، Certificateها، Profileها، Routing، Firewall و Tunnelهای فعال کاربران توسط این قابلیت تغییر یا Restart نمی‌شوند.
- پذیرش Production به ثبت PIDهای قبل/بعد و SHA256 تنظیمات OpenVPN عادی نیاز دارد تا این ایزوله‌بودن اثبات شود.

## بازیابی و بررسی Release
- Runtime State فاقد Secret است و فقط یک تغییر هم‌زمان با Lock غیرمسدودکننده پذیرفته می‌شود.
- Helper جداشده قبل از Mutation اصلی Backup می‌گیرد و نتیجه را با Status Token کوتاه‌عمر به‌صورت `complete` یا `rolled_back` گزارش می‌کند.
- CI شامل Contractهای Backend، Handoff مرورگر، Resume بعد از Restart، Responsive موبایل، Secret Scan و محدودیت اندازه Bundle فعلی است.
- Artifact عمومی v1.0.12 باید Sanitized باشد، SHA256 همراه آن منتشر شود و بعد از انتشار دوباره دانلود و Verify شود.
