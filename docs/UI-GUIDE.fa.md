<div dir="rtl" align="right">

# راهنمای تصویری کامل PVNetwork v1.0.0

این سند صفحات اصلی پنل، دکمه‌های مهم و Workflowهای مدیریتی را توضیح می‌دهد.

> تصاویر برای انتشار عمومی Sanitized شده‌اند و داده‌های واقعی کاربران و زیرساخت در آن‌ها نمایش داده نمی‌شود.

## 1) داشبورد

![Dashboard](./images/ui/dashboard.jpg)

داشبورد برای دید سریع از وضعیت کل Fleet است.

| قسمت | کاربرد |
|---|---|
| Total Live Traffic | نرخ لحظه‌ای مجموع Download/Upload |
| نمودار ۵ دقیقه | روند کوتاه‌مدت ترافیک زنده |
| Online Users | Sessionهای OpenVPN آنلاین |
| Active Nodes | تعداد نودهای سالم و در دسترس |
| Traffic Since Boot | RX+TX تجمعی از زمان Boot نودها |
| Node Traffic & Health | وضعیت، Interface، Uptime، CPU/RAM و ترافیک هر نود |
| Theme | تغییر Light/Dark |
| Language | انتخاب زبان UI |
| Refresh | Refresh دستی داده‌ها |

Rate از اختلاف Sampleها محاسبه می‌شود؛ Counter تجمعی مستقیماً به Mbps تبدیل نمی‌شود.
## 2) مدیریت کاربران

![Users](./images/ui/users.jpg)

صفحه Users چرخه کامل اکانت را مدیریت می‌کند.

| کنترل | کاربرد |
|---|---|
| افزودن کاربر جدید | ساخت کاربر OpenVPN و انتخاب حجم/مدت/نود |
| AnyConnect پیش‌فرض | تعیین فعال بودن AnyConnect برای کاربران جدید |
| Search | جست‌وجوی کاربر |
| Sort | مرتب‌سازی بر اساس زمان، نام، مصرف، انقضا و وضعیت آنلاین |
| Edit | ویرایش مشخصات کاربر |
| Renew | تمدید بدون حذف و ساخت دوباره کاربر |
| Download | دریافت خروجی اتصال از نودهای مجاز |
| AnyConnect | مدیریت وضعیت و اعتبار AnyConnect همان کاربر |
| Domain History | مشاهده Domain activity برای Main Admin |
| Reset Usage | صفر کردن مصرف؛ برای Unlimited دوره ۳۰روزه جدید نیز آغاز می‌شود |
| Activate / Deactivate | فعال یا غیرفعال کردن همان هویت |
| Delete | حذف کنترل‌شده کاربر |
| Copy Link | کپی لینک Subscription |

UUID، Username و Assignmentهای کاربر هنگام Renew حفظ می‌شوند.
### ساخت کاربر

![Add User](./images/ui/workflow-add-user.jpg)

در فرم ساخت کاربر می‌توان حجم، مدت، Assignment نود و AnyConnect را تعیین کرد. مقدار حجم صفر به‌عنوان Unlimited در نظر گرفته می‌شود و برای Unlimited مدت پایه ۳۰ روز است.

### منوی عملیات کاربر

![User Actions](./images/ui/workflow-user-actions.jpg)

منوی سه‌نقطه عملیات اصلی را یکجا در اختیار ادمین قرار می‌دهد و عملیات مخرب از عملیات روزمره جدا شده‌اند.

### Quick Edit داخل ردیف — v1.0.3

![Quick Edit دسکتاپ](./images/v1.0.3/fa/desktop/users-inline-quick-edit.png)

![Quick Edit موبایل](./images/v1.0.3/fa/mobile/users-inline-quick-edit.png)

برای تغییرات پرتکرار از **ویرایش سریع** استفاده کنید. حجم، تاریخ انقضا در حالت‌هایی که Policy اجازه می‌دهد، تعداد اتصال هم‌زمان، وضعیت Active، Node Assignment و Reset Usage در یک پنل قابل کنترل‌اند. روی موبایل/تبلت، Quick Edit از عرض ثابت جدول جدا و به پنل تمام‌عرض تبدیل می‌شود تا Nodeها و دکمه‌های Apply/Cancel/Reset همیشه قابل دسترس باشند. Username فعلاً Read-only است چون تغییر آن نام Client/Profile روی نودها را هم عوض می‌کند؛ Rename امن در `PVN-022` جداگانه پیاده‌سازی خواهد شد.

در تغییر Assignment رفتار محافظه‌کارانه است: حذف نود از Assignment فقط Profile را Deactivate می‌کند و Certificate را حذف نمی‌کند؛ هنگام اضافه‌کردن دوباره، پروفایل غیرفعال قبلی در صورت امکان Reuse می‌شود؛ نود جدیدی که Offline/Drain/Maintenance باشد قبل از Mutation رد می‌شود.

### تمدید کاربر

![Renew User](./images/ui/workflow-renew-user.jpg)

Renew از همان UUID و Username استفاده می‌کند. برای سرویس حجمی سه رفتار وجود دارد: Preserve، Reset و Add Traffic. کاربر Expired بعد از تمدید دوباره فعال و روی نودهای Assignment‌شده Sync می‌شود.

### AnyConnect

![AnyConnect](./images/ui/workflow-anyconnect.jpg)

این پنجره فعال/غیرفعال کردن AnyConnect، مشاهده وضعیت Account و ساخت یا تغییر Credential همان کاربر را مدیریت می‌کند. تغییرات OpenVPN و AnyConnect از یک هویت کاربری مشترک استفاده می‌کنند.
## صفحه Subscription — نسخه v1.0.2

![Subscription دسکتاپ](./images/v1.0.2/fa/desktop/subscription.png)

![Subscription موبایل](./images/v1.0.2/fa/mobile/subscription.png)

صفحه عمومی Subscription وضعیت و مصرف، تاریخ انقضا، تعداد اتصال هم‌زمان، سرور پیشنهادی، دانلود کلاینت‌ها، دستور Linux، اطلاعات AnyConnect و اعلان تمدید را نشان می‌دهد. روی موبایل دکمه‌های Copy/Test/Renew حداقل فضای Touch مناسب دارند، Username و Host طولانی داخل کارت می‌شکنند و خود صفحه نباید Horizontal Scroll داشته باشد. دکمه‌های زبان و Theme نیز در دسترس باقی می‌مانند.

## 3) مدیریت نودها

![Nodes](./images/ui/nodes.jpg)

Node Management وضعیت پایه و Health نودهای OpenVPN را نشان می‌دهد.

| کنترل | کاربرد |
|---|---|
| Add New Node | افزودن نود جدید |
| Refresh | دریافت دوباره فهرست نودها |
| Health Refresh | به‌روزرسانی Health و Routing data |
| Edit | ویرایش مشخصات نود |
| Delete | حذف نود با بررسی Assignmentهای وابسته |

### افزودن نود

![Add Node](./images/ui/workflow-add-node.jpg)

فرم Add Node از حالت Automatic و Manual پشتیبانی می‌کند. در حالت Automatic اطلاعات SSH فقط برای اجرای فرآیند Deploy استفاده می‌شود و نباید داخل مخزن عمومی قرار گیرد. API port، OpenVPN port، protocol و tunnel address قابل تنظیم هستند.

Auto Deploy نباید Firewall را Flush کند، Default Route را عوض کند یا سرویس‌های نامرتبط سرور را حذف کند.
## 4) مدیریت ادمین‌ها و نمایندگان

![Admins](./images/ui/admins.jpg)

این صفحه برای Main Admin است و مدیریت ادمین/Reseller را انجام می‌دهد.

| کنترل | کاربرد |
|---|---|
| Add Admin | ایجاد ادمین یا نماینده جدید |
| Search | جست‌وجوی Username |
| Edit | ویرایش محدودیت‌ها و مشخصات ادمین |
| Delete | حذف با انتخاب Transfer Users یا Delete Users |

### افزودن ادمین

![Add Admin](./images/ui/workflow-add-admin.jpg)

در فرم ساخت نماینده می‌توان Permission/Quotaهای پشتیبانی‌شده را تعیین کرد. هنگام حذف نماینده، انتقال کاربران به Owner دیگر مسیر امن‌تری نسبت به حذف کاربران است.

## 5) مرکز عملیات

![Operations](./images/ui/operations.jpg)

Operations Center ابزارهای عملیاتی چندکاربره و چندنودی را کنار هم قرار می‌دهد.
| ابزار | کاربرد |
|---|---|
| Refresh | دریافت دوباره Dashboard عملیاتی |
| Bulk Activate | فعال‌سازی گروهی UUIDها |
| Bulk Deactivate | غیرفعال‌سازی گروهی UUIDها |
| Bulk Reset Usage | صفر کردن گروهی مصرف |
| Transfer | انتقال Assignment/User workload بین Source و Target |
| Auto Rebalance | اجرای Rebalance پیشنهادی |
| Dry-run Rebalance | مشاهده نتیجه احتمالی بدون اعمال تغییر |
| Usage History | مشاهده تاریخچه مصرف یک UUID |
| Backup/Restore | ساخت، دانلود و Restore بکاپ تأییدشده |

Restore نیازمند فایل معتبر و تأیید صریح است و Progress عملیات نمایش داده می‌شود.

## 6) امنیت پنل

![Security](./images/ui/security.jpg)

| کنترل | کاربرد |
|---|---|
| Rate Limit | محدود کردن نرخ درخواست‌ها |
| IP Allowlist | محدود کردن دسترسی مدیریتی به CIDRهای مجاز |
| TOTP 2FA | ساخت، تأیید یا غیرفعال‌کردن احراز هویت دومرحله‌ای |
| API Token | ساخت Token با نام، Scope و Expiry |
| Revoke | باطل‌کردن Token صادرشده |

مقادیر امنیتی در Screenshotهای عمومی Blur شده‌اند و نباید در Issue/README منتشر شوند.
## 7) مدیریت پیشرفته نودها / Fleet

![Fleet](./images/ui/fleet.jpg)

Fleet Management برای عملیات مرحله‌ای روی چند نود طراحی شده است.

| کنترل | کاربرد |
|---|---|
| Select Nodes | انتخاب نودهای هدف |
| Upgrade | شروع Upgrade کنترل‌شده روی انتخاب‌ها |
| Retry | تکرار Job شکست‌خورده |
| Maintenance | خارج کردن موقت نود از عملیات عادی |
| Leave Maintenance | بازگرداندن نود به حالت عادی |
| Drain | جلوگیری از Session/Assignment جدید و تخلیه کنترل‌شده |
| Resume | بازگرداندن نود Drain‌شده |
| Refresh | تازه‌سازی Health/Version/Job state |

Health، Mode، CPU، RAM، API latency، Online Users، Sessions، Weight و Score برای تصمیم عملیاتی نمایش داده می‌شوند.

## 8) تنظیمات مانیتورینگ

![Monitoring](./images/ui/monitoring.jpg)

Monitoring Settings تنظیم Alertها و Telegram monitoring را مدیریت می‌کند. Save تنظیمات را ثبت می‌کند، Test Telegram یک پیام آزمایشی می‌فرستد و Retry/Refresh وضعیت را دوباره می‌خواند.
## 9) کنترل پهنای‌باند

![Bandwidth](./images/ui/bandwidth.jpg)

Bandwidth Control برای اعمال Policy اضطراری یا مرحله‌ای طراحی شده است.

| کنترل | کاربرد |
|---|---|
| Refresh | تازه‌سازی Settings، Groupها و وضعیت نودها |
| Emergency Off | خاموش‌کردن فوری Policy فعال |
| Preview | مشاهده Target و اثر Policy بدون اعمال |
| Canary | اعمال محدود روی یک نود انتخابی |
| Activate | فعال‌سازی Policy روی Target نهایی |
| Create Group | ساخت گروه کاربری برای Policy |
| Save Members | ذخیره اعضای گروه |
| Delete Group | حذف گروه Policy |

صفحه Node Status نتیجه اعمال Policy روی هر نود و Last Result آخرین عملیات را نمایش می‌دهد.

## Workflow پیشنهادی برای تغییرات حساس

برای عملیات Fleet، Bandwidth، Restore و Update ابتدا Preview/Health/Backup را بررسی کنید، سپس تغییر را روی محدوده کوچک اجرا کنید و بعد از Verification آن را گسترش دهید.

## درباره تصاویر این مستند

تمام Screenshotها صرفاً برای Documentation عمومی ساخته شده‌اند. مقادیر Demo نشان‌دهنده تنظیمات یا ظرفیت واقعی هیچ Deployment مشخصی نیستند.

[بازگشت به README فارسی](../README.fa.md) · [English UI guide](./UI-GUIDE.md)

</div>
