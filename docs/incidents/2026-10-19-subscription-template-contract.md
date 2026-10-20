# Historical subscription template contract error — PVN-1045

Status: queued for the next immutable patch (target60); not fixed in QA59. Three real subscription requests returned 500 on the previous 58 process before the 59 activation. Their nested exception wrappers contain multiple traceback headers, representing three request failures. Private identifiers, caller addresses and raw journals stay outside Git.

The traceback identifies `backend/routers/sub.py:300`, `get_subscription`, with `TypeError: unhashable type: dict`. The handler still calls `TemplateResponse("subscription.html", context_dict)` in frozen 59. The installed locked Starlette 1.6.0 API takes `request` first and `name` second, so this old positional call supplies the dictionary as the template name. This is an inherited compatibility defect, separate from the node-form PVN-1044 correction.

Required next work: reproduce through the actual subscription route in an isolated synthetic ASGI fixture using the pinned dependency; pass request/name/context explicitly; cover valid, missing and unavailable-node states; repeat relevant browser/privacy/contract checks and publish a new immutable version. Existing template-only rendering checks do not establish that this real route's API call is valid.

QA59's successful candidate-launch observation window contains zero fresh traceback/5xx, and its node/UI/cached-profile continuity checks pass. This scoped result does not label the historical subscription defect fixed or certify the whole release Stable. The59 tag/assets stay immutable. [QA59 evidence](../VALIDATION-v1.0.59.md) · [Production scope](../PRODUCTION-v1.0.59.md).

فارسی: سه درخواست واقعیِ اشتراک در فرایند58 و پیش از استقرار59 با خطای500 مواجه شده‌اند. فراخوانی موقعیتی قدیمیِ TemplateResponse با API نسخهٔ Starlette 1.6.0 سازگار نیست؛ دیکشنری context به جای نام قالب تفسیر می‌شود. این ایراد در59 اصلاح نشده و برای patch تغییرناپذیر بعدی با تست واقعی route در محیط ساختگی ثبت است. شناسه‌ها و لاگ خام خصوصی می‌مانند؛ مشاهدهٔ بدون خطای تازه پس از استقرار59 به معنی رفع این ایراد قدیمی نیست.
