# PVNetwork Panel v1.0.10 — مهاجرت سازگار نام‌های پروتکل

`PVN-030` نام‌های داخلی باقی‌مانده متعلق به PVNetwork را بدون قطع Nodeها یا Integrationهای قدیمی به نام‌های جدید منتقل می‌کند.

## رفتار سازگاری

- توکن‌های API جدید با پیشوند `pvn_` ساخته می‌شوند و توکن‌های قدیمی `ovp_` همچنان معتبر می‌مانند و همان Scopeها روی آن‌ها اعمال می‌شود.
- Callbackهای Node می‌توانند `X-PVNetwork-Node-Key` یا Header قدیمی `X-OV-Node-Key` را ارسال کنند.
- اگر هر دو Header با مقدار یکسان ارسال شوند درخواست پذیرفته می‌شود؛ اگر مقدارشان متفاوت باشد درخواست با HTTP 400 رد می‌شود.
- هنگام Upgrade یک Node، Helperهای تزریق‌شده با نام `_pvnetwork_*` ساخته می‌شوند و Aliasهای قدیمی `_ov_*` نیز در فرآیند Upgrade نرمال می‌شوند.

## مواردی که عمداً تغییر نمی‌کنند

- نام‌های upstream شامل `primeZdev/ov-node`، مسیر `/opt/ov-node` و سرویس `ov-node.service` دست‌نخورده می‌مانند.
- Nodeهای فعلی مجبور به Upgrade فوری نیستند.
- Listener اصلی OpenVPN، PKI، پروفایل کاربران و حالت certificate-only عادی هیچ تغییری نمی‌کنند.

## تست انتشار

قبل از Rollout، تست‌های سازگاری پروتکل، کل تست‌های Python، Compile/Static checks، lint/build/audit فرانت‌اند، Browser regression، Secret scan و Production canary اجرا می‌شوند.
