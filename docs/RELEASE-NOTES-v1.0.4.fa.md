# PVNetwork Panel v1.0.4

تاریخ انتشار: 2026-09-19  
Task: `PVN-025` — مالکیت کامل Namespace با نام PVNetwork

## چه چیزهایی تغییر کرد

در این Patch نام‌گذاری Source و Runtime به‌صورت کامل با هویت PVNetwork یکپارچه شده است. Installer، ابزار Lifecycle، سرویس systemd، مسیرهای Application/Config/State، فرمت Backup، شناسه‌های Frontend و Package metadata همگی از نام‌های استاندارد PVNetwork استفاده می‌کنند.

نام‌های استاندارد اصلی:

- مسیر برنامه: `/opt/pvnetwork-panel`؛
- سرویس systemd: `pvnetwork-panel.service`؛
- تنظیمات سیستمی: `/etc/pvnetwork`؛
- State سیستمی: `/var/lib/pvnetwork-panel`؛
- Backup: `/var/backups/pvnetwork-panel` و `pvnetwork-backup-*`؛
- ابزار Lifecycle: `pvnetwork`؛
- کلید زبان Frontend: `pvnetwork_language`.

CI یک Ownership Scan اجباری دارد تا Namespaceهای قدیمی دوباره وارد Source فعلی نشوند.
## سازگاری و ایمنی Production

این نسخه Patch مربوط به Namespace و مالکیت محصول است و عمداً منطق حجم کاربران، Node Assignment، Certificate، Routing، Firewall یا Tunnelها را تغییر نمی‌دهد.

قرارداد Production همچنان اجباری است: Preflight فقط‌خواندنی، Backup تأییدشده Application و PostgreSQL، ثبت مسیر Rollback، Deploy محدود، کمترین Restart لازم، Health داخلی و عمومی و بررسی Integration/Log.

Production در حال حاضر از مسیر و سرویس استاندارد PVNetwork استفاده می‌کند؛ بنابراین Deploy باید Release تأییدشده را با Runtime زنده تطبیق دهد و Rename مخرب را دوباره اجرا نکند.

## به‌روزرسانی

پس از Backup تأییدشده:

```bash
pvnetwork doctor
pvnetwork backup
PVNETWORK_REF=v1.0.4 pvnetwork update
```

اگر هر Health Gate بعد از Deploy شکست خورد، وضعیت ثبت‌شده قبل از Deploy بازیابی می‌شود و Task باز می‌ماند.

## مرحله بعد

`PVN-026` / v1.0.5 قرارداد Production را PostgreSQL-first می‌کند و نام Database/Role زنده را به `pvnetwork_panel` منتقل می‌کند. این Migration عمداً داخل v1.0.4 ادغام نشده است.
