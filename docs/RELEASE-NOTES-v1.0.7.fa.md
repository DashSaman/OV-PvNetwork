# PVNetwork Panel v1.0.7 — Hotfix همگام‌سازی کاربران آنلاین

**Patch task:** `PVN-031`

Dashboard و User Management از قبل منطق مشترک v1.0.6 را داشتند، اما Poll مستقل می‌توانست روی دو Snapshot مجاور بیفتد. v1.0.7 یک Snapshot کوتاه‌عمر سراسری و endpoint سبک و Scope‌شده برای Presence صفحه کاربران اضافه می‌کند.

## ایمنی
- فقط نمایشی است و `active_sessions` مصنوعی نمی‌سازد.
- منطق Device Limit و acquire/heartbeat/release تغییر نمی‌کند.
- Migration دیتابیس ندارد.
- Profile/Certificate/Route/Firewall/Tunnel را تغییر نمی‌دهد.
