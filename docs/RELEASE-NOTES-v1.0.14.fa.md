# PVNetwork Panel v1.0.14 — رگرسیون امنیتی

`PVN-585` مرزهای امنیتی فعلی پنل را به تست‌های دائمی و قابل‌تکرار برای هر Release تبدیل می‌کند. این نسخه Hardening/Regression است و معماری جدید SSO یا RBAC اضافه نمی‌کند.

## مواردی که واقعاً بازتولید و اصلاح شدند

- **هماهنگی IP پشت Nginx:** صفحه Security Settings برای جلوگیری از lockout اولین مقدار `X-Forwarded-For` را می‌خواند، اما Middleware مقدار نهایی افزوده‌شده توسط Nginx محلی را معتبر می‌دانست. حالا هر دو از یک تابع مشترک استفاده می‌کنند.
- **مرز دسترسی API Token:** یک API Token با `type=main_admin` در Security Router می‌توانست مانند ادمین اصلی تعاملی عبور کند. Security، تنظیمات runtime پنل و Backup اکنون یک guard مشترک دارند و API Token را برای عملیات حساس تعاملی رد می‌کنند.
- **اعتبار Prefix توکن:** fallback احراز هویت می‌توانست توکنی با Prefix غیرمجاز را در صورت وجود Hash در دیتابیس بپذیرد. فقط `pvn_` و Prefix قدیمی `ovp_` پذیرفته می‌شوند.
- **طبقه‌بندی Scope:** تشخیص Scope با substring انجام می‌شد و مسیرهای مشابه می‌توانستند اشتباه در گروه users/nodes قرار بگیرند. حالا Prefixهای واقعی API به‌صورت دقیق طبقه‌بندی می‌شوند.

## کنترل‌هایی که از قبل امن بودند

امضای JWT، انقضا، subject/generation ادمین اصلی، غیرفعال‌شدن Admin، جلوگیری از traversal در Backup، ownership، replay توکن تغییرات پنل، SQL parameterization، پوشش routeها، redaction خروجی، CORS، Bearer Auth، escaping در React و permission فایل‌های حساس همگی با تست‌های جدید تأیید شدند.

## Gateهای دائمی جدید

- Security regression suite مستقل در GitHub Actions.
- تست Chromium برای XSS با داده Mock در browser matrix فعلی.
- Probe فقط‌خواندنی و بدون Credential برای Production: health، headerهای امنیتی، بسته‌بودن docs/OpenAPI، رد درخواست بدون Auth و CORS مبدا غیرمجاز.
- Guard استاتیک برای جلوگیری از interpolation مستقیم داده داخل `SQLAlchemy text()`.

## موارد معماری موکول‌شده

هیچ finding جدید Critical/High که نیازمند تغییر معماری باشد بازتولید نشد. مدیریت پیشرفته Session و hardening مربوط به cookie/session همچنان در `PVN-508` و `PVN-528` باقی می‌مانند و در این Release به‌عنوان آسیب‌پذیری قطعی معرفی نمی‌شوند.

## مرز ایمنی Production

تست‌های مخرب یا state-changing فقط روی محیط ایزوله/Canary اجرا می‌شوند. Probeهای Production فقط‌خواندنی و بدون Credential هستند. Node و OpenVPN اصلی در rollout ایزوله می‌مانند؛ Backup/Restore ابتدا verify می‌شود، Canary روی `19002` تست می‌شود، Nginx به `19001` برمی‌گردد و قبل از خاموش‌شدن Canary باید `CANARY_RETIRE_SAFE=YES` ثبت شود.

Release فقط بعد از CI نهایی main، تطبیق Tag، انتشار artifact پاک‌سازی‌شده، SHA256 و دانلود مجدد عمومی از GitHub کامل محسوب می‌شود.
