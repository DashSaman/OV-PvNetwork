# PVNetwork Panel v1.0.13 — PVN-894

PVN-894 فرآیند Release در Production را بعد از اشکال ترتیب Retire کردن Canary در Rollout نسخه v1.0.12 سخت‌گیرانه‌تر می‌کند.

## Guard بستن Canary
- اگر Nginx هنوز به `127.0.0.1:19002` Proxy کند، Retire رد می‌شود.
- اگر پورت اصلی `127.0.0.1:19001` Upstream فعال پنل نباشد، Retire رد می‌شود.
- `nginx -t` باید موفق باشد.
- `/healthz` محلی روی نسخه اصلی باید HTTP 200 باشد.
- URL عمومی `/healthz` که Operator می‌دهد باید HTTP 200 باشد.
- فقط بعد از عبور همه Gateها `CANARY_RETIRE_SAFE=YES` چاپ می‌شود؛ در غیر این صورت Exit Code غیرصفر و `CANARY_RETIRE_SAFE=NO` برمی‌گردد.

## مرز ایمنی
- OpenVPN عادی، Listener سازگاری Router، `ov-node.service`، Certificateها، Profileها، Routing، Firewall و Tunnelهای فعال کاربران تغییر نمی‌کنند.
- این Guard خودش هیچ Processی را Stop نمی‌کند؛ Operator فقط پس از PASS شدن Guard اجازه بستن Canary را دارد.
