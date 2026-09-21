# PVNetwork Panel v1.0.16 — تغییر امن نام کاربری روی چند نود

`PVN-022` امکان تغییر Username را با Job پایدار و بدون حذف/ساخت مجدد کاربر مرکزی اضافه می‌کند.

## حفظ هویت
UUID کاربر تغییر نمی‌کند. مالک، سهمیه، تاریخ انقضا، مصرف/Accounting، محدودیت اتصال، Node Assignmentهای صریح، Credential مبتنی بر UUID در AnyConnect و Credential مبتنی بر UUID/Node در Router/MikroTik حفظ می‌شوند. متن Audit تاریخی بازنویسی نمی‌شود.

## Cutover امن OpenVPN
ابتدا هویت‌های جدید `<username>-<node>` روی تمام نودهای تخصیص‌یافته Stage و Verify می‌شوند. سپس CNهای قدیمی Disable/Disconnect شده، Username در DB به‌صورت اتمیک Commit می‌شود و هویت‌های قبلی فوراً revoke/delete می‌شوند. Grace Period نداریم؛ پس از تکمیل موفق، پروفایل‌های OpenVPN قبلی معتبر نیستند.

فرآیند Rename فقط از عملیات per-user استفاده می‌کند و هیچ `restart` سراسری برای OpenVPN انجام نمی‌دهد.

## رفتار در خطا
قبل از Commit دیتابیس، خطای Stage/Cutover باعث `rollback` ترمیمی می‌شود: هویت قدیمی در صورت فعال‌بودن برمی‌گردد و هویت‌های جدید Stageشده حذف می‌شوند. بعد از Commit، Username جدید معتبر باقی می‌ماند. اگر پاک‌سازی هویت قدیمی کامل نشود، Job در `cleanup_pending` می‌ماند؛ دسترسی قدیمی عمداً دوباره فعال نمی‌شود و Cleanup به‌صورت idempotent قابل Retry است.

Durable lifecycle lock عملیات Edit/Reset/Renew/Node Assignment/Status/Delete متعارض را در زمان Rename متوقف می‌کند و Worker پس از Restart از State ذخیره‌شده ادامه می‌دهد.

## UI و API
Username در Quick Edit همچنان Read-only است. Modal مستقل Rename هشدار باطل‌شدن فوری پروفایل قبلی و قطع Session را نمایش می‌دهد، Nodeهای درگیر و Progress پایدار را نشان می‌دهد، بعد از Refresh Job فعال را بازیابی می‌کند و Retry برای `cleanup_pending` دارد.

## Release gate
تکمیل Production منوط به CI دقیق Head، Backup قابل Rollback، Migration، Canary روی `19002`، بازگشت امن به `19001` با Nginx guard، Rename یک کاربر Synthetic، اثبات حفظ UUID/Accounting/Assignment، ابطال پروفایل قدیمی و صحت پروفایل جدید، ثابت ماندن PID/hash کانفیگ OpenVPN اصلی، Public smoke، Artifact sanitization، SHA256 و دانلود مجدد عمومی است.
