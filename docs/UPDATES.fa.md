# ارتقا، rollback و بازیابی بررسی‌شده

[English](UPDATES.md) · [نصب](INSTALLATION.fa.md) · [کنسول](CLI.fa.md)

## ۱. آماده‌سازی

1. وضعیت نسخه، تغییرات، migration و محدودیت rollback را بخوانید. QA نسخه پایدار پشتیبانی‌شده نیست. tag منتشرشده تغییرناپذیر انتخاب کنید؛ branch منبع update native نیست.
2. `sudo pvnetwork status --json`، `doctor --json`، `database check --json` و `jobs --json` را فقط‌خواندنی اجرا کنید. transaction نیمه‌تمام متعلق به پنل را پیش از تغییر دوم حل کنید.
3. `sudo pvnetwork backup --json` را اجرا و مسیر تأییدشده، آرشیو خصوصی برنامه/runtime و snapshot بومی دیتابیس را نگه دارید. verification شامل rehearsal واقعی Restore و checksum است. پوشه failed نقطه rollback نیست.
4. فضای آزاد، نسخه قبلی نگه‌داشته‌شده، سازگاری schema و transport نود را کنترل کنید. زمان کوتاه نگهداری پنل را هماهنگ و VPN، route، فایروال و سرویس‌های نامرتبط را حفظ کنید.

## ۲. ارتقای نصب واجد شرایط

پس از موجود شدن asset رسمی و عبور از gateها، نمونه انتخاب صریح نسخه QA:

```bash
sudo pvnetwork update v1.0.58 --dry-run --json
sudo pvnetwork update v1.0.58 --yes --json
```

برای نصب قدیمی rooted، گزینه `--adopt-rooted` انتخاب صریح جداست؛ ابتدا `pvnetwork update --help` را بخوانید و مسیر بررسی‌شده را تمرین کنید. پوشه فعال را دستی جایگزین نکنید.

موتور checksum/نسخه را بررسی، بکاپ native تهیه، نسخه stage را build، دیتابیس clone جدا را Restore و migration مجاز و سلامت canary را بررسی می‌کند. سپس پنل وارد maintenance می‌شود، writerهای متعلق به پنل متوقف، بکاپ نهایی quiesced گرفته، migration مجاز اجرا و pointer تعویض و سلامت بررسی می‌شود. فقط پنل در حد نیاز restart و proxy مدیریت‌شده به‌آرامی reload می‌شود؛ VPN نامرتبط خارج از دامنه است.

## ۳. بررسی پس از فعال‌سازی

1. نسخه، سرویس فعال، سلامت محلی/HTTPS عمومی و asset واقعی فعلی UI را کنترل کنید.
2. هویت کاربر/ادمین/نود، تخصیص، حفظ تنظیمات/کلید و خوانایی دیتابیس را بررسی کنید.
3. روند تغییرکرده، مثلاً دانلود نود پیش‌فرض/انتخابی را تست کنید. آزمون تغییردهنده با هویت ساختگی باشد.
4. خطاهای پس از استقرار، وضعیت job، سلامت/PID سرویس‌های دیگر و ترافیک VPN را بررسی کنید.
5. commit، checksum، مسیر بکاپ، restart/maintenance و آمادگی rollback را خصوصی ثبت و فقط شواهد پاک‌سازی‌شده منتشر کنید.

## ۴. تفاوت بازگشت کد و بازیابی داده

`sudo pvnetwork rollback --yes --json` نسخه قبلی یک update native تکمیل‌شده را انتخاب می‌کند. سازگاری schema و transport نود لازم است؛ کد عوض می‌شود و **داده جاری زنده** حفظ می‌شود. این فرمان آرگومان مسیر دلخواه بکاپ نمی‌گیرد.

`sudo pvnetwork restore BACKUP_ID --yes --json` بازیابی صریح داده از ID بکاپ تأییدشده است و اثر متفاوت روی داده/maintenance دارد. ابتدا دامنه و بکاپ را بررسی کنید. Restore آپلود وب قالب و job متناظر خود را دارد. برای بازگشت کد، dump قدیمی را پس از تغییرات تازه کاربران کورکورانه اعمال نکنید.

برای update/settings/data قطع‌شده ابتدا `sudo pvnetwork jobs --json` و سپس `sudo pvnetwork recover --yes --json` همان journal متعلق به پنل را دنبال کنید. عملیات نیمه‌تمام recovery دارد و نباید update تکمیل‌شده فرض شود. پیش از تغییر بعدی نتیجه نهایی و سلامت را بررسی کنید.

## ۵. مرز snapshot

در native v1.0.55 فقط لاگ تشخیصی در حال نوشتن `data/app.log` از snapshot runtime/source کنار گذاشته و فایل زنده حفظ می‌شود. لاگ ناشناخته، بایت کلیدها و اعتماد SSH همچنان کنترل می‌شوند. کلید، `.env`، دیتابیس و فایل runtime بکاپ خصوصی‌اند و نباید در issue عمومی بارگذاری شوند.

[آموزش تصویری بکاپ](UI-GUIDE.fa.md#11-panel-backup-and-restore) · [شواهد انتشار](VALIDATION-v1.0.54.md)
