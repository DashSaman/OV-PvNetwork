# نامزد v1.0.41 — PVN-1025

نصب تازه با بررسی بسته، ابزارهای اختصاصی با نسخه و hash ثابت، staging اتمی، Setup Mode امن و URL واقعی، و default عمومی smoke اصلاح شده‌اند. SQLite و PostgreSQL خالی با metadata و constraintهای جاری و revision نهایی در مسیر اتمی ساخته می‌شوند؛ migrationهای ارتقای تاریخی تغییر نمی‌کنند. نصب و دیتابیس موجود از مسیر نصب تازه رد می‌شوند. [راهنمای نصب و recovery](INSTALLER-CANDIDATE.fa.md).

در checkpoint محلی، ۴۰۵ تست Linux و نصب در سه محیط موقت x86_64 با systemd واقعی عبور کردند. پس از آخرین تغییر کد، CI و regression نهایی روی commit دقیق لازم است. ACME عمومی، ARM64 و VPN خارجی بدون اجرای واقعی تأیید نشده‌اند.

Production تغییر جدیدی نداشته و روی Candidate تأییدشدهٔ 1.0.40 باقی است. gateهای Lifecycle، نود، خصوصی‌سازی و انتشار نهایی باز هستند. از updater قدیمی استفاده نکنید؛ پذیرش میزبان موجود و rollback مسیر مستقل دارند. tag و Artifact منتشرشدهٔ قبلی تغییر نمی‌کند.
