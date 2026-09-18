<div dir="rtl" align="right">

# PVNetwork Panel

**کنترل‌پلین چندنودی OpenVPN با تمدید، نمایندگی، مانیتورینگ، اتوماسیون و یکپارچه‌سازی اختیاری AnyConnect**

**[English](./README.md) · فارسی**

## نسخه پایدار

`v1.0.0` اولین Baseline پایدار و Freeze‌شده عمومی پروژه است. سورس این Release از Snapshot سانیتایزشده Production ساخته شده و عمداً هیچ رمز، کلید، IP یا دامنه عملیاتی، دیتابیس، اطلاعات مشتری، فایل VPN، Private Key یا Certificate واقعی داخل آن قرار نمی‌گیرد.

## نصب سریع

روی سرور تازه Ubuntu 22.04/24.04 یا Debian 12 با کاربر `root`:

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/DashSaman/OV-PvNetwork/main/install.sh)
```

Bootstrap فایل سورس Release `v1.0.0` را دانلود می‌کند، SHA-256 آن را بررسی می‌کند و Installer محلی را اجرا می‌کند. نصب Fresh اگر `/opt/ov-panel` از قبل وجود داشته باشد آن را overwrite نمی‌کند.

## امکانات اصلی

- مدیریت کاربران و چند نود OpenVPN از یک پنل.
- Auto Deploy نود با SSH از داخل Node Management.
- تخصیص کاربر به نودهای انتخابی و محدودیت اتصال همزمان Global.
- حجم، سرویس نامحدود، تاریخ انقضا و تمدید مستقیم بدون حذف اکانت.
- Reset Usage اکانت نامحدود = صفر شدن مصرف + شروع دوره جدید ۳۰ روزه با همان هویت اکانت.
- اعتبارسنجی و Rebuild خودکار Profileهای OpenVPN هنگام دانلود در صورت نیاز.
- AnyConnect اختیاری به‌صورت per-user.
- نمایش CPU، RAM، Uptime، Traffic و Health نودها.
- Drain، Maintenance، Weight، Fleet، Canary و Rollback foundation برای نودها.
- سهمیه حجمی و نامحدود نمایندگان و Ledger مصرف سهمیه.
- عملیات گروهی کاربران و Rebalance خودکار.
- کنترل اضطراری Bandwidth با Fail-open و Rollback.
- Audit Log، API Token، Rate Limit، IP Allow-list و TOTP/2FA.
- Backup/Restore و کنترل‌های عملیاتی سلامت سرویس.
- Usage History و Domain Activity.
- Hookهای مانیتورینگ تلگرام و API یکپارچه‌سازی Mirza.
- صفحه اشتراک برندشده چندزبانه، دانلود کلاینت، پیشنهاد هوشمند نود و Web Push تمدید.

جزئیات: [docs/FEATURES.md](./docs/FEATURES.md) و [docs/FEATURE-MATRIX.md](./docs/FEATURE-MATRIX.md)

## افزودن نود VPN

بعد از نصب پنل:

1. وارد **مدیریت نودها** شوید.
2. **افزودن نود** را بزنید.
3. Auto Deploy با SSH را انتخاب کنید.
4. مشخصات اتصال سرور مقصد را فقط داخل پنل وارد کنید.
5. پنل نصب Node، OpenVPN integration و API مدیریت را انجام داده و نتیجه را Verify می‌کند.

راهنما: [docs/NODE-INSTALLATION.fa.md](./docs/NODE-INSTALLATION.fa.md)

## قانون حریم خصوصی Repository عمومی

موارد زیر هرگز نباید Commit شوند و فقط روی Production یا فضای خصوصی Ops بمانند:

- `.env` و Credentialهای تولیدشده
- Admin/Mirza/API/JWT Secret
- SSH credential و Node API Key
- IP، Domain و Route واقعی زیرساخت
- دیتابیس، Log و اطلاعات مشتری
- فایل `.ovpn`، Private Key، TLS/VAPID Key و Certificate

قبل از انتشار Stable Release، سورس عمومی جداگانه Scan می‌شود. گزارش اسکن داخل Archive نسخه با نام `SECRET-SCAN-REPORT.md` قرار دارد.

## سیاست Release

Baseline `v1.0.0` بعد از انتشار Freeze می‌شود و تغییرات بعدی در Release جدید می‌آیند:

- `1.0.x` = Bugfix/Security fix سازگار
- `1.x.0` = قابلیت جدید بدون Breaking Change
- `2.0.0` = تغییر معماری یا Protocol با Breaking Change

Production محل توسعه نسخه بعدی نیست؛ تغییرات ابتدا جداگانه آماده و تست می‌شوند و بعد با Backup و Health Check Deploy می‌شوند.

جزئیات: [docs/RELEASE-POLICY.md](./docs/RELEASE-POLICY.md)

## Credits

PVNetwork Panel از پروژه‌های MIT-licensed یعنی OV-Panel و OV-Node از PrimeZ مشتق شده و با آن‌ها سازگار است. Attribution اصلی در [NOTICE.md](./NOTICE.md) و [LICENSE](./LICENSE) حفظ شده است.

</div>
