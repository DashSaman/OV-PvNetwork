# PVNetwork Panel v1.0.15 — حفظ OpenVPN در چرخه هر کاربر

`PVN-376` / `PVN-398` Restart سراسری OpenVPN را از عملیات معمول هر کاربر حذف می‌کنند.

## رفتار
- **Enable:** فقط CCD همان Client را ایجاد/ترمیم می‌کند و OpenVPN Restart نمی‌شود.
- **Disable:** CCD همان Client حذف و فقط همان Common Name از Management Socket قطع می‌شود.
- **Delete:** دسترسی همان Client بسته، Session همان CN قطع، Certificate با EasyRSA revoke، CRL به‌صورت اتمیک بازتولید/منتشر و سپس فقط artifactهای PKI و Profile همان Client پاک می‌شوند.
- Upgrade نودهای موجود اکنون Patch چرخه کاربر را نیز نصب می‌کند و فقط Router compatibility را به‌روزرسانی نمی‌کند.

## ایمنی
Listener/Server config اصلی OpenVPN، Routing و Firewall تغییر نمی‌کنند. Patch نود idempotent است و Management Socket فعلی Production را با fallback مسیر قدیمی پشتیبانی می‌کند. Migration دیتابیس لازم نیست.

## گیت تأیید
تست‌های متمرکز باید exact-CN و نبود `systemctl restart` را ثابت کنند و قبل از Production کل CI سبز شود. Rollout Production فقط با Backup قابل‌بازیابی، Compile/API health و اثبات ثابت‌ماندن PID و Hash تنظیمات OpenVPN در Probeهای مصنوعی per-user انجام می‌شود.
## تأیید Production
- CI شاخه اصلی، Hotfix سازگاری Legacy Node و CI نهایی `main` قبل از Patch نهایی Production همگی PASS شدند.
- Rollback point شامل Source، Database و Runtime environment تأیید شد.
- یک CN مصنوعی یکتا روی Node نصب‌شده چرخه Activate -> Disable -> Delete را با موفقیت طی کرد.
- PID و Hash تنظیمات OpenVPN عادی در کل Probe بدون تغییر ماندند.
- CRL بازتولید شد و نسخه منتشرشده با OpenSSL معتبر ماند.
- Health پنل canonical نسخه `1.0.15` را گزارش کرد و پس از بستن Canary، مسیرهای عمومی Health/Panel/Users همگی HTTP 200 ماندند.

Probe واقعی Production همچنین یک ناسازگاری Legacy Node را قبل از Release پیدا و رفع کرد: Lifecycle block اکنون self-contained است و به helper قدیمی `_safe_name` وابسته نیست.
