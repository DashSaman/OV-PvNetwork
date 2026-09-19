# PVNetwork Panel v1.0.8 — سخت‌سازی امنیت Production

**تسک انتشار:** `PVN-028`

![فیلد Pin کردن کلید SSH در v1.0.8](./images/v1.0.8/fa/desktop/ssh-host-key-pinning.png)

این نسخه لایه کنترل پنل را امن‌تر می‌کند، بدون اینکه تجربه اصلی OpenVPN کاربران عوض شود. Listener فعلی OpenVPN، گواهی کاربران و پروفایل‌های certificate-based دست‌نخورده می‌مانند.

## تغییرات امنیتی
- رمز ادمین اصلی از مقدار plaintext در محیط به bcrypt یک‌طرفه منتقل می‌شود و مسیر مهاجرت atomic و تست‌شده دارد.
- مستندات و schema عمومی API در Production تابع `DOC` شده‌اند و health check از `/healthz` استفاده می‌کند.
- Login محدودکننده اختصاصی و سخت‌تری دارد، بدون اینکه مسیرهای integration به آن وابسته شوند.
- Headerهای HSTS، ضد frame، MIME، Referrer، Permissions و CSP اضافه و با UI تست می‌شوند.
- SSH نصب و مدیریت Node دیگر کلید host ناشناخته را خودکار Trust نمی‌کند؛ اتصال اول باید با fingerprint تأییدشده pin شود.
- dependencyهای Python به‌صورت یک مجموعه تست‌شده به‌روزرسانی شده‌اند؛ `pip-audit` هیچ advisory شناخته‌شده‌ای گزارش نمی‌کند و CI جلوی برگشت dependency آسیب‌پذیر را می‌گیرد.
- Bandit برای یافته‌های Medium/High وارد release gate شده است؛ موارد SSH با command ثابت به‌صورت صریح review شده‌اند.
- ابزار firewall جدید inventory-first و reversible است: ruleهای فعلی Tunnel/NFQUEUE را حفظ می‌کند، allowlist صریح می‌خواهد، قبل از تغییر snapshot می‌گیرد و اگر health تأیید نشود rollback تایمردار دارد.

## ایمنی استقرار
نسخه ابتدا روی canary محلی جدا تست می‌شود و سپس backend اصلی جابه‌جا می‌شود. قبل از مهاجرت credential، از برنامه، PostgreSQL و env نسخه rollback گرفته می‌شود. اعمال firewall یک مرحله جدا و نهایی است و اجازه ندارد config مربوط به OpenVPN، Xray یا Tunnel را تغییر دهد.

## OpenVPN فعلی عوض نمی‌شود
برای کاربران عادی همان فایل `.ovpn` مبتنی بر certificate و بدون username/password باقی می‌ماند. سازگاری با Router/MikroTik یک قابلیت opt-in جداگانه است و بخشی از این نسخه نیست.
