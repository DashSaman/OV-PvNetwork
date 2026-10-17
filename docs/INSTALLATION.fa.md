# نصب PVNetwork

[English](INSTALLATION.md) · [README](../README.fa.md) · [آموزش تصویری](UI-GUIDE.fa.md)

## ۱. مسیر درست را انتخاب کنید

نصب تازه برای مقصد خالی و واجد شرایط پنل است. وجود `/opt/pvnetwork-panel`، unit/site پنل، دیتابیس غیرخالی یا اشغال پورت لازم یعنی باید مسیر ارتقا/پذیرش بررسی‌شده نصب موجود را دنبال کنید. روی پنل فعال دوباره نصب تازه اجرا نکنید.

کنترل میزبان Ubuntu 22.04/24.04 و Debian 12، معماری x86_64/aarch64، حداقل RAM یک GiB و دیسک آزاد سه GiB را پوشش می‌دهد. شواهد واقعی نصب Setup Mode نسخه v1.0.55 برای هر سه توزیع روی x86_64 و ARM64 واقعی موجود است؛ [اعتبارسنجی](VALIDATION-v1.0.55.md) را ببینید. ACME عمومی واقعی و شبکه VPS مستقل همچنان gate تکمیل‌نشده جدا دارند. v1.0.55 نامزد QA است؛ فرمان آن را فقط پس از موجود شدن assetهای تغییرناپذیر و خواندن یادداشت نسخه اجرا کنید.

## ۲. نصب در Setup Mode خصوصی

1. با دسترسی root مجاز وارد و پورت‌ها، سرویس‌ها و منابع فعلی را بررسی کنید.
2. روی مقصد تازه bootstrap پین‌شده را اجرا کنید:

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/DashSaman/OV-PvNetwork/v1.0.55/install.sh)
```

3. تا نتیجه نهایی تأییدشده صبر کنید. نسخه، SHA256 و metadata آرشیو رسمی بررسی و ابزار، dependency، دیتابیس، build، سرویس و proxy پیش از فعال‌سازی آماده می‌شوند.
4. با root اطلاعات ورود اولیه را خصوصی از `/etc/pvnetwork-panel/initial-credentials.txt` بخوانید. فایل 0600 برای درج در لاگ نصب یا issue عمومی نیست.
5. روی رایانه خودتان forward رمزگذاری‌شده SSH باز کنید؛ USER و SERVER را با حساب و میزبان خودتان جایگزین کنید:

```bash
ssh -L 18443:127.0.0.1:18443 USER@SERVER
```

6. SSH را باز نگه دارید و در مرورگر محلی `http://127.0.0.1:18443/panel/` را باز کنید. Setup Mode روی loopback است؛ URL عمومی یا controller قابل‌دسترسی نود راه دور نیست.

## ۳. مقصد تازه با HTTPS عمومی

1. دامنه واقعی با DNS درست و ایمیل مجاز ACME آماده کنید. پورت‌های عمومی 80/443 باید آزاد و اعتبارسنجی ACME با سیاست شبکه فعلی قابل‌دسترسی باشد.
2. روی مقصد تازه واجد شرایط اجرا کنید:

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/DashSaman/OV-PvNetwork/v1.0.55/install.sh) --domain panel.example.com --email operator@example.com
```

3. ابتدا دامنه و ایمیل نمونه را عوض کنید. تا صدور گواهی، سایت HTTP متعلق به پنل فقط challenge را سرو می‌کند و مسیرهای دیگر 503 می‌دهند.
4. تا صدور گواهی، بررسی syntax Nginx و سلامت/UI محلی و عمومی صبر کنید. فقط از URL نهایی تأییدشده استفاده کنید؛ شکست صدور گواهی یعنی HTTPS عمومی آماده نیست.
5. وضعیت تمدید مدیریت‌شده را با CLI بررسی کنید. Installer برای موفق شدن ACME فایروال را تغییر نمی‌دهد.

برای Setup Mode موجود، جهت افزودن TLS دوباره Fresh Install اجرا نکنید. `pvnetwork tls --help`، proxy و گواهی فعلی را بررسی و انتقال TLS را جدا و بررسی‌شده انجام دهید. تغییر path/port به‌تنهایی گواهی عمومی صادر نمی‌کند.

## ۴. بررسی و افزودن اولین نود

```bash
sudo pvnetwork version --json
sudo pvnetwork status --json
sudo pvnetwork doctor --json
sudo pvnetwork database check --json
sudo pvnetwork jobs --json
```

1. نسخه نصب‌شده، فعال بودن پنل، سلامت محلی و دیتابیس را تأیید کنید. در صورت تنظیم HTTPS، دسترسی عمومی را جدا بسنجید.
2. وارد شوید، زبان/تم را انتخاب و [نصب نود](NODE-INSTALLATION.fa.md) را دنبال کنید.
3. کاربر ساختگی تست بسازید و [پروفایل و اتصال واقعی VPN](UI-GUIDE.fa.md#3-profiles-subscriptions-and-anyconnect) را بررسی کنید.
4. پیش از کاربران واقعی بکاپ native تأییدشده و کپی خصوصی خارج از میزبان تهیه کنید.

![داشبورد پس از ورود با داده Demo](images/v1.0.54/fa/desktop/dashboard.png)

## ۵. مسیرها و بازیابی

| مسیر | کاربرد |
| --- | --- |
| `/opt/pvnetwork-panel` | اشاره‌گر برنامه فعال |
| `/opt/pvnetwork-panel-releases` | نسخه آماده/جاری/قبلی برنامه |
| `/var/lib/pvnetwork-panel/runtime` | env و داده خصوصی نصب تازه |
| `/etc/pvnetwork-panel` | اطلاعات ورود، کلید و journal پایدار |
| `/opt/pvnetwork-panel-tools` | ابزار پین‌شده خصوصی |
| `/var/backups/pvnetwork-panel` | بکاپ native خصوصی و تأییدشده |

تکرار دقیق نصب تکمیل‌شده فقط سلامت را بررسی می‌کند و اطلاعات ورود را دوباره نمی‌سازد. سورس متفاوت با همان شماره نسخه رد می‌شود. در قطع نصب تازه، journal خصوصی را بخوانید و فقط برای همان transaction ناموفق متعلق به پنل، bootstrap همان نسخه را با `--recover` تکرار کنید. بازیابی update/settings با `sudo pvnetwork recover --yes --json` پس از بررسی jobs انجام می‌شود؛ این دو زمینه recovery متفاوت‌اند.

journal و تشخیص شکست را حفظ کنید؛ برای اجبار نصب تازه دیتابیس یا پوشه را پاک نکنید. [جزئیات نصب](INSTALLER-CANDIDATE.fa.md)، [کنسول](CLI.fa.md) و [ارتقا/rollback](UPDATES.md) را بخوانید.
