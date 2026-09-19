# PVNetwork Panel v1.0.5 — PVN-026 انتخاب Node هنگام ساخت User

## چه چیزی تغییر کرده است

در Add User محل ساخت Profile به‌صورت صریح قابل انتخاب است. همه Nodeهای Available به‌صورت پیش‌فرض انتخاب می‌شوند و Nodeهای Offline، Drain و Maintenance دیده می‌شوند اما Disabled هستند. ادمین می‌تواند قبل از Submit هر Node غیرضروری را بردارد و Backend هویت OpenVPN را فقط روی Assignment ثبت‌شده Provision می‌کند.

![Node Selector دسکتاپ](./images/v1.0.5/fa/desktop/user-create-node-selector.png)

![Node Selector موبایل](./images/v1.0.5/fa/mobile/user-create-node-selector.png)

## قرارداد Backend

- فیلد `CreateUser.node_ids` برای Compatibility اختیاری است.
- اگر `node_ids` ارسال نشود، همه Nodeهایی که Active هستند و Drain/Maintenance نیستند انتخاب می‌شوند.
- Nodeهای صریح قبل از ساخت User یا تغییر سهم نماینده Validate می‌شوند.
- Assignment انتخاب‌شده در همان Transaction دیتابیس User و وضعیت اختیاری AnyConnect ثبت می‌شود.
- Provision نود فقط بعد از Commit و فقط برای Assignment ذخیره‌شده انجام می‌شود.
- خرابی موقت API یک Node باعث حذف User معتبر نمی‌شود؛ Reconciler بعداً Profile جاافتاده را ترمیم می‌کند.

## رفتار Reconciler

وقتی برای User ردیف Assignment وجود دارد، همان ردیف‌ها مرجع نهایی هستند. Reconciler دیگر `user_nodes` اضافی نمی‌سازد و نمی‌تواند User را بی‌اجازه روی Node جدید گسترش دهد. Userهای Legacy که هیچ Assignment صریحی ندارند رفتار قبلی all-available را حفظ می‌کنند. Nodeهای Drain/Maintenance وارد عملیات Reconcile نمی‌شوند.

## Verification قبل از Production

- Regression متمرکز Create User / Assignment / Quick Edit / Brand: تعداد 32/32 PASS.
- کل Unit/Governance Python: تعداد 58/58 PASS.
- Python/Shell/JSON syntax و `uv lock --check`: PASS.
- ESLint و Production Build فرانت‌اند: PASS.
- Runtime npm audit: صفر Vulnerability و Bundle در محدوده بودجه CI.
- Browser Smoke مربوط به Node Selector در فارسی/انگلیسی و عرض‌های 360/390/768/1440: PASS.
- Full Responsive، Quick Edit و Subscription regression gateهای قبلی: PASS.

## ایمنی Production

این نسخه Migration دیتابیس ندارد. Deploy باید طبق قانون پروژه با Backup تأییدشده، Canary روی همان Commit، Cutover محدود Backend/Frontend، کمترین Restart لازم، Health داخلی/عمومی و Rollback آماده انجام شود. Routing، Firewall، Tunnel، Certificate نودها و سرویس‌های نامرتبط خارج از Scope هستند.
