# Frontend Dependency Security Candidate — PVN-1023

Target release: `v1.0.38` (not published or deployed).

The locked Axios version fails the current npm runtime dependency audit. The compatible update to `1.20.0` addresses the upstream advisories. Two development-only dependency updates also clear the full audit: brace-expansion `1.1.21` and source-map-js `1.2.2`.

References: [Axios advisory](https://github.com/advisories/GHSA-vh66-26gq-q6x8), [brace-expansion advisory](https://github.com/advisories/GHSA-q2hr-2g5m-vwhr), [source-map-js advisory](https://github.com/advisories/GHSA-68fv-2mgg-jv7q).

The updated HTTP client initially increased the main chunk above the existing 990000-byte limit. A separate HTTP-client chunk keeps the main bundle at 940185 bytes without raising the limit or changing application flows.

Validation: `npm ci`, `npm audit --omit=dev --audit-level=high`, full `npm audit --audit-level=high`, lint and build pass. All existing admin browser smoke scripts and subscription responsiveness pass on a local build with synthetic API data. The responsive matrix covers Persian/English, nine widths and nine routes. These are UI regressions, not real VPN/node-bootstrap E2E tests.

Deployment remains gated on exact-head Linux CI, release metadata/artifact verification, backups and explicit authorization for the live host. Frontend deployment must add all newly referenced chunks before switching the index atomically. Retain the previous index and referenced chunks for rollback; no backend or VPN restart is needed for this dependency change.

## فارسی

این نامزد انتشار، وابستگی‌های دارای هشدار امنیتی را به نسخه سازگار اصلاح می‌کند. تست audit کامل، lint، build و تست‌های موجود مرورگر با داده ساختگی عبور کرده‌اند. برای حفظ سقف اندازه فایل، کتابخانه HTTP در یک فایل build جدا قرار گرفته است.

این تغییر هنوز منتشر یا روی Production مستقر نشده است. تست واقعی نصب نود و اتصال VPN از تست رابط کاربری جداست و نباید بدون اجرای واقعی موفق اعلام شود. استقرار فرانت‌اند باید با بارگذاری تمام فایل‌های جدید و تعویض اتمیک index انجام شود؛ نیازی به ری‌استارت VPN ندارد.
