<div dir="rtl" align="right">

# Production Handoff — OV-PvNetwork

آخرین به‌روزرسانی: **2026-09-18**

این فایل خلاصه‌ی عملیاتیِ تغییرات ریز Production است تا در چت/جلسه‌ی بعدی لازم نباشد رفتارهای مهم از روی حافظه یا حدس دوباره ساخته شوند.

> **امنیت مخزن:** این Repository عمومی است. عمداً Password، API Key، Private Key، دیتابیس، فایل‌های `.ovpn` کاربران و IPهای مدیریتی حساس در این سند ذخیره نشده‌اند. مقادیر Secret باید فقط روی Production باقی بمانند.

## 1. وضعیت فعلی Production

- پنل اصلی روی `/opt/ov-panel` اجرا می‌شود.
- سرویس اصلی: `ov-panel.service`
- سیستم Production پنل: Ubuntu 24.04 LTS
- Fleet عملیاتی فعلی شامل نودهای Finland، Germany، USA و Turkey2 است.
- نود جدید **Turkey2** با Node ID `10` در دیتابیس ثبت شده است.
- Endpoint کلاینت Turkey2:

```text
open.softarg.ir:1197/UDP
```

- API نود روی TCP/9090 است و نباید Public-open باشد.
- در آخرین Sync تاییدشده، Turkey2 دارای `66/66` Assignment معتبر بود:

```text
CREATED=0
SKIPPED=66
FAILED=0
USER_SYNC=PASS
```

`SKIPPED` در این بررسی به معنی این بود که پروفایل معتبر قبلاً روی نود وجود داشت و Download/API verification موفق بود.

- نود قدیمی Turkey نباید صرفاً با اضافه‌شدن Turkey2 حذف شود؛ حذف/جایگزینی باید تصمیم جداگانه و صریح باشد.

## 2. قانون مهم Production Safety

روی نودی که سرویس دیگری هم دارد، Auto Deploy/Debug نباید سرویس‌های موجود را خراب کند.

مواردی که در Turkey2 وجود داشت و باید حفظ شوند:

- `x-ui` / Xray
- PostgreSQL
- Tunnel/interfaceهای موجود مانند `hw787` و `hs787`
- Ruleهای NAT/SNAT و MSS موجود
- Default route فعلی سرور

### کارهایی که در Production ممنوع‌اند

```text
iptables -F
nft flush ruleset
تغییر کورکورانه Default Route
Restore کامل Firewall بدون بررسی Ruleهای قبلی
حذف نود قدیمی فقط برای جایگزینی نود جدید
Echo کردن API Key/Password در Log یا Git
```

هر تغییر Firewall باید فقط Rule موردنظر را اضافه/حذف کند.

## 3. NodeRequests — نکته‌ی مهم IP:PORT

در `backend/node/requests.py`، constructor آدرس را این‌طور نگه می‌دارد:

```python
self.address = f"{address}:{port}"
```

بنابراین `check_node()` باید URL را با همان `self.address` بسازد:

```python
api = f"http://{self.address}/sync/status"
```

نباید دوباره `self.port` به URL اضافه شود؛ در این کلاس `self.port` الزاماً Attribute مستقل نیست.

Header سازگار با OV-Node فعلی:

```python
self.headers = {
    "key": api_key,
    "api-key": api_key,
}
```

Header اصلی موردنیاز Endpoint فعلی `key` است.

## 4. OV-Node و OpenVPN template compatibility

OV-Node v1.3.6 در `core/setting/core.py` هنوز ممکن است به مسیر قدیمی زیر اشاره کند:

```text
/etc/openvpn/server/client-common.txt
```

اما installer جدید OpenVPN روی Production از این فایل استفاده می‌کند:

```text
/etc/openvpn/server/client-template.txt
```

Auto Deploy باید در Runtime این Compatibility patch را اعمال کند تا `change_config()` روی `/sync/status` شکست نخورد.

Client template نود Turkey2 بعد از Sync تنظیمات باید حداقل شامل این خطوط باشد:

```text
proto udp
remote open.softarg.ir 1197
```

## 5. systemd و ساخت Profile در /root

Profileهای نود در مسیر زیر ساخته می‌شوند:

```text
/root/<client-name>.ovpn
```

به همین علت این hardening قدیمی باعث Fail شدن Profile Builder می‌شد:

```ini
ProtectHome=read-only
```

برای معماری فعلی سرویس OV-Node باید اجازه‌ی نوشتن Profile در `/root` داشته باشد. تنظیم Production فعلی:

```ini
ProtectHome=no
```

این مورد داخل Auto Deploy نیز اصلاح شده است.

## 6. Profile Builder اختصاصی

Helper فعلی:

```text
/usr/local/sbin/ov-build-client-profile
```

وظیفه‌ی آن:

1. اعتبارسنجی نام Client
2. بررسی PKI موجود
3. عدم Rotate کردن Certificate سالم بدون نیاز
4. Rebuild کردن `.ovpn` از PKI موجود در صورت ممکن
5. ساخت Certificate جدید فقط وقتی Entry معتبر وجود ندارد
6. اضافه‌کردن CA / cert / key / tls material به Profile
7. ساخت CCD موردنیاز
8. اعتبارسنجی نهایی Profile

Profile معتبر باید حداقل:

- بیشتر از 500 بایت باشد
- `<ca>...</ca>` داشته باشد
- `<cert>...</cert>` داشته باشد
- `<key>...</key>` داشته باشد
- خط `remote` داشته باشد

نکته: وجود HTTP 200 در `/sync/user` به‌تنهایی برای اثبات ساخت Profile کافی نیست؛ فایل/Download نهایی نیز باید Verify شود.

## 7. User sync روی نود جدید

Flow امن برای Sync نود جدید:

1. Node Health check
2. ثبت/Update Node در DB
3. Sync Assignmentهای موجود
4. برای هر User نام Client بر اساس الگوی زیر:

```text
<username>-<node-name>
```

مثال:

```text
pv-102-Turkey2
```

5. اگر Profile معتبر موجود بود، Skip
6. اگر نبود، Create
7. بعد از Create، Download/Profile verification
8. گزارش `CREATED / SKIPPED / FAILED`

Sync طولانی باید Progress قابل مشاهده داشته باشد؛ تابعی که بدون Output چندصد User را Sync کند ممکن است ظاهراً Hang به نظر برسد.

## 8. `/sync/status` و ترتیب ساخت status

در upstream، `status` ابتدا باید ساخته شود:

```python
status = {"status": "running"}
```

و بعد helperهای سفارشی روی آن `update()` شوند.

قرار دادن این خطوط قبل از تعریف `status` باعث `UnboundLocalError` می‌شود:

```python
status.update(_ov_dashboard_network_snapshot())
status.update(_ov_openvpn_online_snapshot())
```

همچنین helperهای Monitoring نباید بتوانند Health endpoint را کامل Down کنند. Snapshotهای فرعی باید Fail-safe باشند.

## 9. Network Metrics — رفتار صحیح Production

مشکل Turkey2 این بود که CPU/RAM دیده می‌شد ولی Upload/Download، Traffic، Uptime و Online data صفر یا Waiting بودند.

روش صحیح Production:

- Node شمارنده‌های خام کارت شبکه را برمی‌گرداند.
- داشبورد از اختلاف نمونه‌ها، Rate لحظه‌ای Mbps را حساب می‌کند.

Snapshot فعلی باید این فیلدها را برگرداند:

```text
network_interface
boot_time
uptime
rx_bytes
tx_bytes
traffic_bytes
```

انتخاب Interface:

1. ابتدا Default Route از `/proc/net/route`
2. اگر پیدا نشد، اولین Interface فعال و غیرمجازی
3. `lo` و Interfaceهای واضح مجازی مثل `tun*`, `tap*`, `wg*`, `docker*`, `veth*`, `br-*` برای WAN-rate نادیده گرفته شوند

شمارنده‌ها از:

```python
psutil.net_io_counters(pernic=True)
```

خوانده می‌شوند.

آخرین تست واقعی Turkey2:

```text
IFACE=eth0
HTTP=200
RX/TX counters increasing
RX_RATE ~= 0.16 Mbps during test
TX_RATE ~= 0.002-0.004 Mbps during test
TURKEY2_NETWORK_METRICS=PASS
```

این Rate نمونه‌ی همان لحظه است و مقدار ثابت/هدف محسوب نمی‌شود.

## 10. OpenVPN online snapshot

OpenVPN server فعلی Status file دارد و Online session snapshot باید از Runtime status خوانده شود. خرابی parser یا نبود فایل status نباید `/sync/status` را 500 کند.

قاعده:

```text
Monitoring enrichment may fail; node health must remain available.
```

## 11. Firewall API 9090

API نود نباید برای تمام Internet باز باشد.

ترتیب منطقی Ruleها:

```text
ALLOW loopback -> tcp/9090
ALLOW panel-server -> tcp/9090
DROP everyone else -> tcp/9090
```

Ruleها باید Persistent شوند (`netfilter-persistent save`).

مهم: هیچ‌وقت برای Hardening پورت 9090 کل Firewall را Flush نکنید؛ نود ممکن است Ruleهای Tunnel/NAT دیگری داشته باشد.

## 12. Auto Deploy — Fixهای دائمی فعلی

`backend/node/deploy.py` در Production برای نودهای بعدی این Compatibilityها را دارد:

- نصب/فعال‌سازی OV-Node و OpenVPN
- Profile Builder اختصاصی
- Patch User management
- `ProtectHome=no`
- تبدیل `client-common.txt` به `client-template.txt`
- ترتیب صحیح `status` و helperهای dashboard
- Fail-safe بودن snapshotهای Monitoring
- Firewall API نود
- Compile/health verification

### نکته‌ی مهم

این Auto Deploy از نظر Source و `py_compile` تایید شده، اما بعد از آخرین Fixها هنوز باید یک بار روی **VPS خالی آزمایشی** از صفر End-to-End تست شود. تا قبل از آن نباید صرفاً بر اساس Compile، آن را 100% battle-tested فرض کرد.

## 13. Subscription UI و پرچم Turkey2

روی Windows/Chrome، Emoji پرچم `🇹🇷` ممکن است به صورت حروف `TR` نمایش داده شود.

برای همین در UI Subscription نباید برای Turkey2 به Emoji سیستم‌عامل وابسته بود. راه پایدار استفاده از SVG واقعی پرچم ترکیه است.

Template فعلی Subscription:

```text
frontend/templates/subscription.html
```

هدف UI:

```text
Turkey2 + Turkey SVG flag
```

نه Globe عمومی و نه Emoji که روی بعضی Windowsها `TR` رندر شود.

## 14. رفتار Dashboard

داشبورد Admin باید برای هر Node این داده‌ها را مستقل نشان دهد:

- Online status
- Upload/Download لحظه‌ای
- Total traffic
- Online OpenVPN sessions
- Uptime
- CPU
- RAM

Poll/Rate نباید بر اساس مقدار تجمعی مستقیم به Mbps تبدیل شود؛ Rate باید از Delta بین دو Sample و Delta-time محاسبه شود.

## 15. Backup قبل از Patch

قبل از تغییر مستقیم روی Production همیشه Backup فایل هدف ساخته شود، مثل:

```text
router.py.bak-<purpose>-YYYYMMDD-HHMMSS
requests.py.bak-<purpose>-YYYYMMDD-HHMMSS
deploy.py.bak-<purpose>-YYYYMMDD-HHMMSS
```

برای تغییرات بزرگ‌تر از `ovpv backup` یا Export production استفاده شود.

## 16. Source of truth

Production در طول زمان Patchهای کوچک زیادی گرفته است. اگر Git و Production اختلاف داشتند:

1. Production را بدون Backup overwrite نکنید.
2. ابتدا Snapshot/Export sanitized بگیرید.
3. Diff بگیرید.
4. Secret scan انجام دهید.
5. فقط تغییرات Review‌شده را به Git منتقل کنید.

راهنمای Snapshot: [`PRODUCTION-SNAPSHOT.md`](./PRODUCTION-SNAPSHOT.md)

## 17. Checklist نود جدید

قبل از اعلام موفقیت نود جدید:

```text
[ ] ov-node active
[ ] OpenVPN active
[ ] OpenVPN UDP/TCP listener درست
[ ] /sync/status HTTP 200
[ ] API key header درست
[ ] client-template endpoint درست
[ ] test profile ساخته و دانلود می‌شود
[ ] remote/proto داخل profile درست
[ ] existing users sync شده‌اند
[ ] FAILED=0 یا Failها بررسی شده‌اند
[ ] network_interface درست شناسایی شده
[ ] RX/TX counters افزایش پیدا می‌کنند
[ ] realtime Mbps روی Dashboard ظاهر می‌شود
[ ] CPU/RAM/Uptime/Online metrics درست
[ ] tcp/9090 فقط برای Panel/loopback مجاز
[ ] سرویس‌های قبلی سرور سالم‌اند
[ ] NAT/Tunnel/Default route دست‌نخورده‌اند
[ ] Auto Deploy source هم Fix شده، نه فقط نود جاری
```

## 18. اصل کلی برای ادامه توسعه

- اول Read-only inspection، بعد Patch دقیق.
- از Regex/Replace کورکورانه روی Functionهای Production خودداری شود مگر قبلش Source دقیق دیده شده باشد.
- Health check نباید به Featureهای تزئینی Monitoring وابسته شود.
- ساخت User باید Idempotent باشد.
- Profile موجود و معتبر نباید بی‌دلیل Rotate شود.
- Secretها هیچ‌وقت وارد Git نشوند.
- نود جدید ابتدا کنار نود قدیمی اضافه شود؛ حذف نود قدیمی مرحله‌ی جداست.

</div>
