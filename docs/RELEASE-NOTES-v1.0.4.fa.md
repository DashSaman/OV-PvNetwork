# PVNetwork Panel v1.0.4

## محدوده تغییر

`PVN-025` مالکیت کامل PVNetwork روی سورس و Runtime را تثبیت می‌کند. شناسه محصول پنل قدیمی در هیچ فایل یا مسیر Track‌شده‌ای مجاز نیست و CI از برگشت دوباره آن جلوگیری می‌کند.

## تغییرات

- مسیر اصلی برنامه: `/opt/pvnetwork-panel`.
- سرویس اصلی systemd: `pvnetwork-panel.service`.
- مسیرها و شناسه‌های Backup/Restore، Push، Monitoring، Fleet و Config با نام PVNetwork یکدست شدند.
- Installer/Update نسخه‌ها را از ریپوی `DashSaman/OV-PvNetwork` می‌گیرد.
- نسخه Python package، API، Frontend package و Release روی `1.0.4` یکسان شد.
- زبان مرورگر با کلید `pvnetwork_language` ذخیره می‌شود و یک مقدار معتبر قدیمی با الگوی عمومی `*_language` قابل انتقال است.
- در نصب‌های SQLite اگر فقط یک فایل دیتابیس موجود باشد همان فایل دوباره استفاده می‌شود تا هنگام تغییر نام مسیر، دیتابیس خالی جدید ساخته نشود.
- Attribution لایسنس MIT مربوط به پایه اولیه حفظ شده ولی برند محصول قدیمی وارد سورس PVNetwork نمی‌شود.

## ایمنی Production

قبل از تغییر Runtime باید Backup کامل برنامه و Dump بومی PostgreSQL گرفته و Verify شود. Runtime جدید PVNetwork ابتدا روی یک پورت Local موقت در کنار سرویس فعلی بالا می‌آید. فقط بعد از پاس شدن API/UI، nginx به‌شکل Atomic به Runtime جدید سوییچ می‌شود. پس از آن Health داخلی/عمومی، دیتابیس، Logها و Mirza بررسی می‌شوند و سپس Runtime قبلی کنار گذاشته می‌شود.

در این Release نباید Firewall، Default Route، Tunnel، VPN Node، Certificate یا سرویس نامرتبط تغییر کند. اگر هر Gate بعد از سوییچ Fail شود، nginx و Runtime فوراً به وضعیت قبل برمی‌گردند.
