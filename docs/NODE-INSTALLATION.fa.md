<div dir="rtl" align="right">

# نصب نود

در PVNetwork Panel v1.0.0 روش پیشنهادی نصب نود، **Auto Deploy با SSH از داخل خود پنل** است.

## قبل از شروع

یک VPS پشتیبانی‌شده Ubuntu/Debian با دسترسی root SSH لازم است. اگر روی سرور مقصد سرویس دیگری فعال است، قبل از Deploy باید Firewall، NAT، Tunnel و Routeهای موجود حفظ شوند. هیچ‌وقت کل Firewall را Flush نکنید و Default Route را کورکورانه تغییر ندهید.

## نصب خودکار

1. وارد **مدیریت نودها** شوید.
2. **افزودن نود** را انتخاب کنید.
3. گزینه **Auto Deploy با SSH** را فعال نگه دارید.
4. نام نود، SSH Address/Port، نام کاربری/رمز SSH، Endpoint و Port/Protocol مربوط به OpenVPN و تنظیمات API نود را وارد کنید.
5. Deploy را شروع کنید و Console پیشرفت را تا پایان Verify باز نگه دارید.
6. بعد از پایان، Health/Metrics نود را بررسی و یک User آزمایشی روی همان نود ایجاد/دانلود کنید.

Flow نصب، نسخه سازگار Node را نصب می‌کند، Compatibility/Profile patchهای PVNetwork را اعمال می‌کند، سرویس مدیریت را می‌سازد و API نود را Verify می‌کند.

## نکات ایمنی

روی نودهای Shared، سرویس‌های دیگر، Ruleهای NAT/SNAT/MSS، Tunnelها و Routeهای موجود باید دست‌نخورده بمانند. دسترسی API نود باید به Loopback و منبع مدیریتی پنل محدود شود. Credentialهایی که در فرم Deploy وارد می‌شوند نباید در Repository عمومی Commit شوند.

## چک نهایی

- سرویس Node فعال باشد.
- OpenVPN فعال باشد.
- Health endpoint جواب دهد.
- CPU/RAM/Uptime/Network داخل پنل دیده شود.
- ساخت User آزمایشی روی نود موفق باشد.
- فایل دانلودی CA/Certificate/Key و Remote/Protocol صحیح داشته باشد.
- سرویس‌ها و Routeهای قبلی سرور مقصد سالم مانده باشند.

</div>
