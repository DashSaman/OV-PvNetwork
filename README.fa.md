<div dir="rtl" align="right">

# OV-PvNetwork

**کنترل‌پلین چندنودی و Production-Oriented برای OpenVPN با قابلیت یکپارچه‌سازی اختیاری AnyConnect**

[English](./README.md) · **فارسی**

---

OV-PvNetwork یک توزیع توسعه‌یافته و عملیاتی بر پایه‌ی اکوسیستم متن‌باز OV-Panel / OV-Node است. هدف پروژه این است که مدیریت ساده‌ی کاربران OpenVPN را به یک سیستم چندنودی واقعی با نصب آسان، مانیتورینگ، همگام‌سازی کاربران، تحویل مطمئن کانفیگ، آپدیت و Rollback تبدیل کند.

> نسخه‌ی فعلی مخزن `1.0.0-rc1` است. پایه‌ها به‌صورت ثابت Pin شده‌اند و از `latest` کورکورانه استفاده نمی‌شود. نسخه‌ی Stable نهایی بعد از Export و پاک‌سازی Snapshot واقعی Production منتشر می‌شود تا چیزی از روی حافظه یا حدس بازسازی نشود.

## نصب با یک دستور

روی سرور تازه و با کاربر `root`:

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/DashSaman/OV-PvNetwork/main/install.sh)
```

بعد از نصب:

```bash
ovpv status
ovpv doctor
ovpv update
ovpv backup
ovpv rollback
```

## امکانات اصلی

- مدیریت چند نود OpenVPN از یک پنل مرکزی
- Desired-state برای تخصیص کاربران به نودها
- Reconciler کم‌مصرف برای ساخت/ترمیم کانفیگ کاربران روی نودها
- پایه‌ی نصب خودکار نود و Pin کردن نسخه‌های OV-Node و OpenVPN installer
- ساخت و ترمیم خودکار فایل‌های `.ovpn`
- اعتبارسنجی `<ca>`، `<cert>` و `<key>` قبل از تحویل کانفیگ
- اعمال `remote`، پروتکل و پورت از تنظیمات دیتابیس هنگام دانلود
- خواندن واقعی کارت شبکه: Interface، RX/TX، Uptime و Traffic
- داشبورد لحظه‌ای ادمین با یک Endpoint تجمیعی، جلوگیری از درخواست همزمان و توقف Poll در تب مخفی
- مدل نرخ ترافیک Server-side / per-node برای جلوگیری از Spike ناشی از Cache و زمان‌بندی مرورگر
- صفحه Subscription اختصاصی Private Network و انتخاب هوشمند نود
- کنترل امن‌تر چرخه‌ی عمر نود و حذف Assignment-aware
- Health check، Backup و Rollback
- Branding اختصاصی، Favicon و لینک‌های پروژه
- پایه‌ی چندزبانه
- Integration hooks برای AnyConnect / Session Control، Bandwidth Control، Monitoring، Domain Activity و Fleet Operations

ماتریس کامل وضعیت قابلیت‌ها: [docs/FEATURES.md](./docs/FEATURES.md)

## سخت‌افزار پیشنهادی

### سرور پنل

| سطح | CPU | RAM | Disk | کاربرد |
|---|---:|---:|---:|---|
| حداقل | 1 vCPU | 1 GB | 10 GB | تست / نصب کوچک |
| پیشنهادی | 2 vCPU | 2 GB | 20 GB SSD | Production معمولی |
| پرترافیک | 4 vCPU | 4 GB+ | 40 GB+ SSD | نود/کاربر/مانیتورینگ زیاد |

### هر نود VPN

| سطح | CPU | RAM | Disk |
|---|---:|---:|---:|
| حداقل | 1 vCPU | 512 MB | 5 GB |
| پیشنهادی | 1–2 vCPU | 1 GB+ | 10 GB+ |

توان عبوری واقعی بیشتر از Disk به کیفیت شبکه، قدرت Crypto CPU، MTU/Route و تعداد Session همزمان وابسته است.

## سیستم‌عامل

- Ubuntu 22.04 LTS
- Ubuntu 24.04 LTS
- Debian 12 به‌صورت best-effort در مواردی که پکیج‌های upstream تفاوت دارند

## معماری

```text
                  ┌────────────────────────────┐
                  │       OV-PvNetwork        │
                  │      Panel / API / UI     │
                  └─────────────┬──────────────┘
                                │
                   Assignment / Metrics / API
                                │
          ┌─────────────────────┼─────────────────────┐
          │                     │                     │
    ┌─────▼─────┐         ┌─────▼─────┐        ┌─────▼─────┐
    │ OV-Node A │         │ OV-Node B │  ...   │ OV-Node N │
    │ OpenVPN   │         │ OpenVPN   │        │ OpenVPN   │
    └───────────┘         └───────────┘        └───────────┘
```

## آپدیت و Rollback

آپدیت پروژه باید Transactional باشد: ابتدا Preflight و Backup، سپس دریافت نسخه، اعمال تغییرات و Migration، Build/Compile، Health check و در صورت شکست Rollback. جزئیات در [docs/UPDATES.md](./docs/UPDATES.md).

## Snapshot واقعی Production

چون این پروژه طی چندین مرحله روی Production توسعه پیدا کرده، مخزن یک Exporter امن دارد که سورس واقعی سرور را بدون `.env`، Database، API Key، Private Key، Certificate، پروفایل کاربران و Logها خروجی می‌گیرد. این Snapshot مبنای Stable 1:1 خواهد بود.

راهنما: [docs/PRODUCTION-SNAPSHOT.md](./docs/PRODUCTION-SNAPSHOT.md)

## امنیت

فایل‌های Secret، دیتابیس، کلیدها، `.ovpn` کاربران، SSH Password و TLS Private Key نباید وارد Git شوند. برای جزئیات [SECURITY.md](./SECURITY.md) را بخوانید.

## لینک‌ها

- GitHub: `https://github.com/DashSaman/OV-PvNetwork`
- ربات تلگرام: `https://t.me/pvnetwork_bot`
- Upstream OV-Panel: `https://github.com/primeZdev/ov-panel`
- Upstream OV-Node: `https://github.com/primeZdev/ov-node`

## اعتبار و مجوز

OV-PvNetwork بر پایه‌ی پروژه‌های MIT-licensed مربوط به PrimeZ ساخته شده است. Attribution اصلی در [NOTICE.md](./NOTICE.md) و [LICENSE](./LICENSE) حفظ شده است.

</div>
