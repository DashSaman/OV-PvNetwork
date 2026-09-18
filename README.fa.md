<div dir="rtl" align="right">

# OV-PvNetwork

**کنترل‌پلین چندنودی Production-Oriented برای OpenVPN با یکپارچه‌سازی اختیاری AnyConnect**

[![Version](https://img.shields.io/badge/version-1.0.0-brightgreen?style=flat-square)](./VERSION)
[![Ubuntu](https://img.shields.io/badge/Ubuntu-22.04%20%7C%2024.04-E95420?style=flat-square&logo=ubuntu&logoColor=white)](#نیازمندیها)
[![License](https://img.shields.io/badge/license-MIT-green?style=flat-square)](./LICENSE)

[English](./README.md) · **فارسی**

OV-PvNetwork بر پایه OV-Panel / OV-Node ساخته شده و امکانات لازم برای استفاده واقعی چندنودی را اضافه می‌کند: مدیریت کاربران، تمدید، AnyConnect، سلامت نودها، مانیتورینگ، امنیت پنل، عملیات گروهی، کنترل پهنای‌باند، بکاپ/بازیابی و ابزارهای نصب و به‌روزرسانی امن‌تر.

> تمام تصاویر نسخه عمومی **Sanitized** هستند؛ نام کاربران، آدرس‌ها، کلیدها، رمزها، UUIDها، مقادیر ترافیک و شناسه‌های واقعی Production عمداً مخفی یا با داده نمونه جایگزین شده‌اند.

## نمای تصویری پنل

### داشبورد، کاربران و نودها

![داشبورد، کاربران و نودها](./docs/images/ui/01-control-plane.jpg)

### مدیریت ادمین، مرکز عملیات و امنیت

![مدیریت ادمین، مرکز عملیات و امنیت](./docs/images/ui/02-admin-security.jpg)
### مدیریت پیشرفته نود، مانیتورینگ و کنترل پهنای‌باند

![مدیریت پیشرفته، مانیتورینگ و پهنای‌باند](./docs/images/ui/03-operations.jpg)

برای مشاهده تک‌تک صفحات، دکمه‌ها و Workflowهای اصلی:

- [راهنمای کامل تصویری فارسی](./docs/UI-GUIDE.fa.md)
- [Complete English UI guide](./docs/UI-GUIDE.md)

## امکانات نسخه 1.0.0

| بخش | امکانات اصلی |
|---|---|
| کاربران | ساخت، ویرایش، فعال/غیرفعال، حذف، تمدید، Reset Usage، دانلود پروفایل و لینک اشتراک |
| تمدید | تمدید کاربر Expired بدون حذف، تمدید نامحدود، حالت‌های حفظ/ریست/افزایش حجم |
| AnyConnect | فعال/غیرفعال برای هر کاربر، ساخت یا تغییر رمز، هویت مشترک کاربر |
| نودها | افزودن و ویرایش نود، Health، Assignment، حذف کنترل‌شده |
| Fleet | Health Score، Maintenance، Drain/Resume، Upgrade و Retry کنترل‌شده |
| مانیتورینگ | ترافیک زنده، CPU/RAM/Uptime، تنظیمات هشدار تلگرام |
| امنیت | IP Allowlist، Rate Limit، TOTP 2FA، API Token با Scope و Expiry |
| عملیات | عملیات گروهی کاربران، انتقال/Rebalance، تاریخچه مصرف و Audit/Operations |
| پهنای‌باند | Emergency Off، Preview/Canary/Activate Policy، گروه‌ها و وضعیت نودها |
| بکاپ | ساخت و دانلود بکاپ تأییدشده و Restore با تأیید صریح |
| Integration | API میرزا، API نود OpenVPN و Hookهای اختیاری AnyConnect/ocserv |
## نصب سریع

روی یک سرور **تازه** و با کاربر `root` اجرا کنید:

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/DashSaman/OV-PvNetwork/v1.0.0/install.sh)
```

Installer به Tag ثابت `v1.0.0` متصل است و از Branch توسعه‌ای `latest` به‌صورت کورکورانه استفاده نمی‌کند.

بعد از نصب:

```bash
ovpv status
ovpv doctor
ovpv version
ovpv backup
ovpv update
ovpv rollback
```

اگر روی سرور شما از قبل OVPanel یا سرویس‌های دیگری فعال است، Fresh Installer را مستقیم اجرا نکنید؛ ابتدا مسیر Update/Migration و Backup را بررسی کنید.

مستندات:

- [نصب](./docs/INSTALLATION.md)
- [معماری](./docs/ARCHITECTURE.md)
- [آپدیت و Rollback](./docs/UPDATES.md)
- [تمدید کاربران](./docs/RENEWAL.md)
- [مقایسه امکانات](./docs/FEATURE-MATRIX.md)
- [Roadmap](./ROADMAP.md)
## معماری

```text
                         ┌──────────────────────────────┐
                         │        OV-PvNetwork         │
                         │       Panel / API / UI      │
                         └──────────────┬───────────────┘
                                        │
                    assignment / health / metrics / profile API
                                        │
             ┌──────────────────────────┼──────────────────────────┐
             │                          │                          │
      ┌──────▼──────┐            ┌──────▼──────┐            ┌──────▼──────┐
      │  OV-Node A  │            │  OV-Node B  │     ...    │  OV-Node N  │
      │  OpenVPN    │            │  OpenVPN    │            │  OpenVPN    │
      └─────────────┘            └─────────────┘            └─────────────┘
```

Integrationهای اختیاری می‌توانند شامل AnyConnect/ocserv، Mirza، Telegram و Policyهای مانیتورینگ/پهنای‌باند باشند.

## نیازمندی‌ها

| جزء | حداقل | پیشنهادی |
|---|---:|---:|
| پنل | 1 vCPU / 1 GB RAM / 10 GB | 2 vCPU / 2 GB RAM / 20 GB SSD |
| نود VPN | 1 vCPU / 512 MB RAM / 5 GB | 1–2 vCPU / 1 GB+ RAM / 10 GB |

هدف Installer: Ubuntu 22.04 LTS، Ubuntu 24.04 LTS و Debian 12 با Best-effort در تفاوت پکیج‌های Upstream.
## چرخه امن Production

در Updateهای OV-PvNetwork هدف این است که سرویس بدون تغییر مخرب و بدون Overwrite کورکورانه جلو برود:

1. Preflight و بررسی فضای آزاد.
2. Backup قبل از Update.
3. اعمال Release و Migration هدف.
4. Build و Syntax Check.
5. Restart فقط سرویس موردنیاز.
6. Health Verification محلی.
7. Rollback در صورت شکست Verification.

در Node Automation نیز نباید Firewall کامل Flush شود، Default Route کورکورانه عوض شود یا سرویس‌های نامرتبط حذف شوند.

## سیاست Release

- `v1.0.0` خط پایه Stable است.
- نسخه‌های `1.0.x` برای Fixهای سازگار هستند.
- نسخه‌های `1.x.0` قابلیت جدید سازگار اضافه می‌کنند.
- نسخه Major می‌تواند تغییر معماری یا رفتار Breaking داشته باشد.
- هر تغییر Production-visible باید در `CHANGELOG.md` ثبت و با GitHub Release جدید منتشر شود.

## امنیت مخزن عمومی

`.env`، دیتابیس، API/JWT Secret، SSH Credential، Private Key، TLS Material، فایل `.ovpn` کاربران و Screenshot واقعی حاوی اطلاعات Production نباید Commit شوند. تصاویر این README با داده‌های Demo و Blur منتشر می‌شوند.

راهنمای امنیت: [SECURITY.md](./SECURITY.md)

## اعتبار پروژه

OV-PvNetwork از OV-Panel / OV-Node با مجوز MIT مشتق شده است. Attribution پروژه Upstream در [NOTICE.md](./NOTICE.md) و [LICENSE](./LICENSE) حفظ شده است.

</div>
