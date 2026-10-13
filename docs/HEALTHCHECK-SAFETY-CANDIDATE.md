# Bounded Self-Healing Candidate — PVN-1024

Target: `v1.0.40`, following the dependency-security and smoke-gate patches. This candidate is not published or deployed.

The original healthcheck restarts a node when its configuration/key is absent, ignores intentionally stopped units and can escalate a timed-out restart into force-kill/start. The revised helper checks loaded/running state, skips unconfigured local nodes and uses a bounded systemd `try-restart`. Attempts are limited to one per 300 seconds; a failed restart extends the delay to 900 seconds and reports failure for manual diagnosis. Cooldown state is local to `/run` and resets on reboot.

Authenticated node health probes retain the existing GET-with-JSON contract. HTTP client/authentication/schema errors cause a diagnostic failure without repair; the received status remains meaningful if curl also reports a truncated response. No OpenVPN, routing or firewall operation is added.

Validation: 11 executable fixture regressions pass after reproducing the original failures and the two independently reviewed boundary defects. Existing rollout guard tests (three) and Bash syntax/compilation pass. Live deployment, exact-head Linux CI and release gates remain pending.

Deployment must back up the existing installed helper and its source, verify the tested hashes, switch only the helper/source, and observe the next existing timer invocation. Do not force a healthcheck repair on Production for testing. Rollback restores the two original helper/source files. No service restart is required to update the helper.

## فارسی

این اصلاح، نبود تنظیمات یا کلید نود را دلیل ری‌استارت نمی‌داند و سرویس توقف‌داده‌شده را خودکار روشن نمی‌کند. مسیر SIGKILL حذف شده و تلاش‌های ترمیم محدود شده‌اند. خطای احراز هویت یا قرارداد API باید تشخیص داده شود و باعث ری‌استارت نمی‌شود.

۱۱ تست رفتاری و تست‌های موجودِ guard عبور کرده‌اند. این نتیجه، ادعای استقرار یا تأیید نهایی Production نیست. هنگام استقرار، فقط فایل helper و منبع آن با بکاپ و امکان برگشت تغییر می‌کنند؛ نیازی به ری‌استارت VPN نیست.
