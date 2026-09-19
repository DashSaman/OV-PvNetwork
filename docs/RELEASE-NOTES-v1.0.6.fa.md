# PVNetwork Panel v1.0.6 — یکسان‌سازی شمارش کاربران آنلاین

**Task:** `PVN-027`

![شمارش مشترک کاربران آنلاین — داشبورد](./images/v1.0.6/fa/desktop/online-truth-dashboard.png)

![شمارش مشترک کاربران آنلاین — Users موبایل](./images/v1.0.6/fa/mobile/online-truth-users.png)

## تغییرات نسبت به v1.0.5

Dashboard و User Management اکنون برای وضعیت Online از یک لایه مشترک و صرفاً نمایشی استفاده می‌کنند. Session heartbeatهای تازه‌ی مرکزی همچنان مرجع‌اند؛ اگر یک Node قدیمی یا ناقص کاربران زنده را در session hook مرکزی گزارش نکند، snapshot مستقیم `/sync/usage` همان Node فقط برای نمایش، کمبود را جبران می‌کند.

- کاربران آنلاین بر اساس UUID کاربر PVNetwork بین Nodeها Deduplicate می‌شوند.
- Client مستقیم فقط وقتی map می‌شود که Username آن با یک User فعلی پنل و suffix دقیق نام Node تطابق داشته باشد.
- Profileهای قدیمی/یتیم روی Node دیگر عدد کلی **کاربران آنلاین** را بزرگ نمی‌کنند.
- اگر یک User روی چند Node آنلاین باشد در عدد کلی فقط یک بار شمرده می‌شود؛ برای شمارش اتصال همان User، در نبود جزئیات مرکزی حداقل تعداد Nodeهای مشاهده‌شده نگه داشته می‌شود.
- Cache کوتاه و stale grace محدود مانع Offline شدن لحظه‌ای کاربران در timeout کوتاه Node می‌شود.
- خطای poll یک Node هیچ session مرکزی معتبر و تازه‌ای را حذف نمی‌کند.

## ایمنی Enforcement

این Patch فقط برای Observability است. هیچ row مصنوعی داخل `active_sessions` نوشته نمی‌شود، Device Limit و منطق acquire/heartbeat/release تغییر نمی‌کند. Raw online/session count هر Node همچنان روی Node Card باقی می‌ماند؛ فقط عدد کلی کاربران آنلاین به Userهای واقعی و فعلی PVNetwork محدود و یکسان می‌شود.

## تست

تست‌ها merge بین central/direct، Dedup چندنودی، Username و نام Node دارای خط‌تیره، client ناشناخته، خطای موقت poll و stale-cache grace را پوشش می‌دهند. Browser regression عمداً مجموع raw Nodeها را متفاوت از shared user truth قرار می‌دهد و الزام می‌کند Dashboard و User Management در فارسی/انگلیسی و موبایل/دسکتاپ یک عدد یکسان نمایش دهند.

## Upgrade / Rollback

Migration دیتابیس نداریم. فقط Backend/Frontend پنل تغییر می‌کند. قبل از Deploy از برنامه و PostgreSQL Backup گرفته می‌شود، Canary موازی تست می‌شود، Proxy به‌صورت Atomic سوییچ می‌شود و فقط در صورت نیاز `pvnetwork-panel.service` Restart می‌شود. VPN Nodeها، Route، Firewall، Certificate و Tunnelها خارج از محدوده این Patch هستند.
