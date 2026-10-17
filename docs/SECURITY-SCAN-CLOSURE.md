# Security scan closure and remediation — PVN-1030 / PVN-1034

The original native Codex Security scan is **completed and sealed**, with five indexed findings: one High and four Medium. Completion succeeded on `2026-10-17T14:56:22Z`; the separate read-only canonical contract validator returned `valid`. This closes the outstanding workbench finalization task. It does not turn the explicitly partial review into an independent audit or certify a newer release automatically.

فارسی: پرونده اسکن اولیه رسماً تکمیل و مهر نهایی شد؛ پنج یافته، شامل یک High و چهار Medium، ثبت شده‌اند و اعتبارسنج مستقل فایل‌های نهایی موفق است. این یافته‌ها مربوط به کد قدیمی نسخه۴۵ هستند؛ اصلاح آن‌ها در۴۶/۵۰ انجام شده و در نسخه۵۶ باقی است. پوشش بررسی همچنان partial است و نتیجه، گواهی ممیزی مستقل یا اعلام Stable نیست.

## Source identity and scope

- Scan ID: `563334e9-7b5a-42ba-a9a6-e3ae7c41d2cb`.
- Reviewed immutable source: [`659f30c307f95871db843697797430e6f0f98c8b`](https://github.com/DashSaman/OV-PvNetwork/commit/659f30c307f95871db843697797430e6f0f98c8b), candidate v1.0.45. The scan was not silently retargeted to v1.0.56.
- Current QA source used for remediation comparison: [`490af88fdc86b9306300620b5d2c8ba281186410`](https://github.com/DashSaman/OV-PvNetwork/commit/490af88fdc86b9306300620b5d2c8ba281186410), immutable v1.0.56. Its artifact and six public native guest results remain in [validation evidence](VALIDATION-v1.0.56.md).
- Canonical findings SHA256: `c8c0627be57f6ecd353249cdf15d6378434ae6721339b5baa88501ea302ced30`.
- Canonical coverage SHA256: `11360fb8e3fccabbfbadfd5d777704d9fbf7d4943b44f21a8d814d9f08ecacf9`.

The generated report, manifest, findings, coverage and SARIF remain in the private native scan store. This public document is a sanitized closure and remediation mapping, not a replacement for those sealed files. No canonical scan evidence was manually edited to force completion.

## Findings and existing protections

| Historical source45 finding | Severity | Correction retained in v1.0.56 | Regression evidence |
|---|---|---|---|
| Reseller presence/dashboard leaks another tenant's bearer subscription UUID | High | v1.0.46 filters counts and rates by ownership on fresh and cached responses, while retaining the private global cache and main-admin visibility | `tests/test_user_read_security.py`: cross-tenant presence, fresh/cached dashboard, cache preservation and main-admin cases |
| Customer-selected Push endpoint reaches arbitrary HTTPS destinations | Medium | v1.0.46 shared transport enforces approved origins, all-public DNS answers, pinned destination and TLS hostname verification; redirects/retries are disabled | `tests/test_push_transport.py`: private/mixed/rebound DNS, IP/TLS binding, origin parsing, actual Web Push encryption and shared sender |
| Earlier duplicate Push test route bypasses the intended delivery budget | Medium | v1.0.46 keeps one route, a persisted per-user reservation, bounded concurrent deliveries and off-event-loop sending | `tests/test_push_dispatch.py`: route uniqueness, repeat/new subscription, failure budget, expiry, independent-session race and saturation |
| `users:read` token can reset accounting through a mutating GET | Medium | v1.0.46 makes detail/session GET read-only and moves reset to a write-scoped POST; legitimate unlimited renewal remains | `tests/test_user_read_security.py`, `tests/test_security_scope_regression.py`: unchanged accounting on reads/denial, ownership and authorized reset |
| Stored node label enters executable subscription QR attributes | Medium | v1.0.50 puts escaped strings in inert data attributes and uses fixed click/keyboard listeners | `tests/test_subscription_qr_context.py`, `frontend/tests/subscription-qr-security.mjs`: actual Jinja decoding, hostile synthetic label, click/Enter/Space and real vendored QR SVG |

The first four corrections were verified in [v1.0.46 CI](https://github.com/DashSaman/OV-PvNetwork/actions/runs/38947574882); the QR correction was verified in [v1.0.50 CI](https://github.com/DashSaman/OV-PvNetwork/actions/runs/38964051393). The current immutable v1.0.56 [exact-source CI](https://github.com/DashSaman/OV-PvNetwork/actions/runs/39040481367) also executes these regressions. These historical findings are not five newly discovered, unfixed vulnerabilities in v1.0.56. The native scan's occurrence state describes its old source, rather than a remediation patch applied to that frozen checkout.

Fresh closure checks: canonical sealed-contract validation PASS; actual local Chromium QR matrix PASS in24 EN/FA, light/dark, mobile/desktop and native100/125/150% zoom cases, each with click/Enter/Space. Six portable transport/template tests pass locally. API route tests require Linux (`fcntl`); Windows import failures are recorded as environment limitations, never counted as passes. Linux CI remains the authoritative API-regression environment.

## Coverage and remaining tests

Coverage is still **partial**. The original source review was sequential, without an independent baseline; it did not probe live provider/internal-network behavior or claim line-by-line review of every asset. Four legacy deferred rows remain in the sealed coverage metadata even though their original candidate IDs also appear in the validated findings above. Their status text was not erased or rewritten after sealing. Completion indexed all five findings without warnings; it did not prove those metadata rows disappeared.

Already feasible without an empty VPS: immutable public bootstrap/fresh/repeat on Ubuntu22.04/24.04 and Debian12, both x86_64 and real ARM64; real isolated Nginx certificate activation with the same master PID and failed-syntax refusal; scoped API/security regressions; private archive/recovery fixtures; actual disposable dual-auth OpenVPN handshake; core browser/QR/contrast/layout and public-material checks. Read their exact scope and skips in [v1.0.56 validation](VALIDATION-v1.0.56.md). The isolated handshake does not certify an independent public node lifecycle.

Public ACME issuance/renewal and a full separate external VPS/node/client network lifecycle still require an eligible disposable host, controlled test DNS and an authorized external path. The owner has no empty VPS available. Busy live services are not replacement test targets. Full screen-reader/WCAG/icon/typography and pixel-baseline certification also remains deferred; existing scoped browser checks do not certify it.

This closure changes documentation only. It performs no Production deploy, restart, live certificate rotation, database write, node repair, route or firewall change. Supported Stable remains v1.0.37; public QA remains v1.0.56 and the live panel remains v1.0.55. Published tags and assets are unchanged.

فارسی: تست‌های قابل اجرا در محیط‌های دورریختنی، از جمله نصب تازه و تکراری شش مهمان، TLS ساختگی واقعی Nginx، رگرسیون امنیت و handshake آزمایشی VPN، شواهد دارند. صدور عمومی ACME، چرخه کامل نود روی VPS مستقل و ارزیابی جامع دسترس‌پذیری هنوز تأیید نشده‌اند. سرورهای شلوغ جای VPS آزمایشی نیستند؛ این ادامه فقط مستندات و اعتبارسنجی است و سرویس زنده را تغییر نمی‌دهد.
