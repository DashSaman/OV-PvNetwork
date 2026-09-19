<div dir="rtl" align="right">

# PVNetwork Panel v1.0.3

**Task این Patch:** `PVN-205` — پروفایل/جزئیات کاربر + Quick Edit داخل ردیف.

![Quick Edit دسکتاپ](./images/v1.0.3/fa/desktop/users-inline-quick-edit.png)

![Quick Edit موبایل](./images/v1.0.3/fa/mobile/users-inline-quick-edit.png)

## چه چیزی نسبت به v1.0.2 تغییر کرد؟

- گزینه **ویرایش سریع / Quick Edit** به عملیات هر کاربر اضافه شد.
- حجم، تاریخ انقضا در حالت‌های مجاز، تعداد اتصال هم‌زمان، Active و Node Assignment از یک پنل قابل تغییرند.
- Reset Usage را می‌توان Queue کرد و همراه Apply اجرا کرد.
- در موبایل/تبلت، Editor از عرض ثابت جدول جدا و تمام‌عرض می‌شود.
- Username فعلاً Read-only است تا Rename چندنودی امن در `PVN-022` جداگانه پیاده‌سازی شود.

## ایمنی Multi-Node

حذف نود از Assignment باعث حذف Certificate/Profile نمی‌شود و فقط Profile همان نود Deactivate می‌شود. هنگام اضافه‌کردن دوباره، Profile غیرفعال قبلی در صورت امکان Reuse می‌شود. نود جدیدی که Offline، Drain یا Maintenance باشد قبل از Mutation رد می‌شود. Sync ویرایش/Status نیز فقط روی نودهای Assigned انجام می‌شود.

## تست و Verify

Release Gate شامل 37 تست Python/Unit/Governance، ESLint، Python Compile، Build Production فرانت، Dependency Audit/Bundle Budget، Browser smoke مخصوص Quick Edit، Matrix کامل ۲ زبان × ۹ عرض × ۹ Route، تست Responsive صفحه Subscription، JSON/Shell syntax و Secret/Private-material guard عمومی است.

## Upgrade / Rollback

این نسخه Migration دیتابیس ندارد. قبل از Deploy بکاپ تأییدشده بگیرید. فقط فایل‌های لازم Panel/Backend/Frontend تغییر می‌کنند؛ Firewall، Default Route، Tunnel و سرویس‌های نامرتبط نباید دست‌کاری شوند. در صورت نیاز فقط `pvnetwork-panel` Restart و سپس HTTP داخلی/عمومی، OpenAPI و Error log بررسی می‌شود. اگر Health fail شد به Backup/Release تأییدشده v1.0.2 برگردید.

</div>
