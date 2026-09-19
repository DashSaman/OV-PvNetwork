<div dir="rtl" align="right">

# PVNetwork Panel v1.0.2

**محدوده Patch:** PVN-111 — Responsive Subscription page.

![Subscription دسکتاپ فارسی](./images/v1.0.2/fa/desktop/subscription.png)

![Subscription موبایل فارسی](./images/v1.0.2/fa/mobile/subscription.png)

## چه چیزی تغییر کرد؟
- دکمه Test notification، کپی Linux و Copyهای AnyConnect در موبایل حداقل Touch target حدود 44px دارند.
- Username، Host و Credential طولانی داخل Card باقی می‌مانند و صفحه Horizontal Overflow نمی‌گیرد.
- تست Chromium روی عرض‌های 360/375/390/430/768/1024/1440 و هر دو حالت فارسی RTL و انگلیسی LTR اجرا می‌شود.
- Screenshotهای عمومی فقط از داده Demo و `example.invalid` استفاده می‌کنند.

## آپدیت و Rollback
این Patch Migration دیتابیس ندارد. در Production فقط Template مربوط به Subscription تغییر می‌کند و در صورت نیاز به پاک‌شدن Cache، فقط سرویس پنل Restart می‌شود. Backup تأییدشده قبل از Deploy حفظ می‌شود و در صورت Fail شدن Health Check، Template قبلی برگردانده می‌شود.

## ایمنی
هیچ تغییر عمدی در Firewall، Default Route، Tunnel، VPN Node، هویت کاربر یا Certificate وجود ندارد.

[English release notes](./RELEASE-NOTES-v1.0.2.md)

</div>
