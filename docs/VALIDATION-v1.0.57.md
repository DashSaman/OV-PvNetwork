# v1.0.57 validation — PVN-1041

Status: **verified public QA; no Production deployment**. Supported Stable remains v1.0.37 and the live panel remains v1.0.55. No live service, certificate, database, node, route or firewall mutation occurred.

## Immutable source, artifact and native installation

- Published source `ebdde263e328a978d4aff46f72563a65efb24414`; [QA release](https://github.com/DashSaman/OV-PvNetwork/releases/tag/v1.0.57), source archive SHA256 `b4302c2c3bdfbca046a2cdfdba622d9cbc55f8222d19127c587eeca0266a8d86`. Anonymous checksum/archive downloads match89,648,535 bytes; 94,455,542 expanded bytes / 1,050 members. Git export preserves executable modes/LF scripts and excludes private/runtime material. Tags and assets are immutable.
- Exact [push CI39049357518](https://github.com/DashSaman/OV-PvNetwork/actions/runs/39049357518) and [PR CI39049361781](https://github.com/DashSaman/OV-PvNetwork/actions/runs/39049361781): all 8 jobs PASS.733 discovered unit/governance tests with80 explicit skips; separate82 root fixtures,38 security tests,37 router tests with one explicit external-SSH skip. Real disposable dual-auth VPN handshake, dependency/static audits, lint/build and privacy guards PASS. Largest JS799,030 bytes stays below 990,000. Skips are not passes.
- [Public x86 bootstrap39050586411](https://github.com/DashSaman/OV-PvNetwork/actions/runs/39050586411) and [public ARM bootstrap39050590638](https://github.com/DashSaman/OV-PvNetwork/actions/runs/39050590638): all 6 native guests PASS, Ubuntu 22.04/24.04 and Debian 12 on each architecture. Each downloads the official bootstrap/archive, verifies the exact SHA and exercises fresh installation, preserving repeat, systemd/proxy/UI assets, SQLite/private permissions and installed CLI. ARM checks an actual aarch64 runner and arm64 guest. No emulation pass is claimed. The x86 public branch intentionally reuses the earlier exact-source validation and runs only its three native jobs.
- All 4 inherited TLS fixtures run in every public guest, including actual private Nginx served-certificate replacement with the same master PID and failed-syntax refusal. This does not test public ACME issuance/renewal. The Windows-built archive is byte-identical to all three exact-source Linux CI archives.
- The [tag CI](https://github.com/DashSaman/OV-PvNetwork/actions/runs/39050438944) and final PR continuation checks remain independently visible. Later documentation/test-only evidence commits do not replace the published artifact. Runtime paths must remain identical to this immutable source before merge.

## Accessibility evidence

| Check | Actual result |
|---|---|
| Actual admin/login routes |80 views:9 admin routes plus unauthenticated login × EN/FA × light/dark ×390/1440px. Exact URL/direction assertions prevent silent Dashboard redirects. |
| Dialogs and menus |136 openings across17 dialogs; both open row/mobile menus are scanned.228 axe-core4.14.0 scans PASS with zero definite violations and one deliberately failing unnamed-input negative control. No axe rules are disabled. |
| Keyboard/focus |Tab/Shift+Tab containment, Escape, connected invokers, menu arrows/Home/End, skip link, visible focus, login alert and reduced-motion checks PASS.144 outline measurements pass3:1;4 dark Node Archive gradient cases remain manual. |
| Exact focus return |A separate actual-browser check confirms the exact pre-modal invoker after two animation frames in all 136 openings. The continuation CI persists this stronger assertion and verifies unique visible mobile-menu ID references. |
| Responsive/native zoom |108 combinations: EN/FA × themes ×9 widths ×100/125/150% real Chromium zoom;216 views/432 representative dialog openings PASS. After the final light helper correction, all 54 light combinations repeat PASS. Additional final focus/menu checks:12 combinations/48 openings/68 outline measurements PASS. Widths:360,375,390,430,768,1024,1366,1440,1920. |
| Subscription |Actual Jinja page and open QR:8 EN/FA/theme/width cases,16 axe scans, keyboard containment/exact return PASS;16 contrast incomplete groups retained. Existing hostile-label QR24-case click/Enter/Space/real-SVG regression also passes in Linux CI. |
| Local/static/public docs |39 portable tests/0skips, lint/build/npm runtime audit, both frozen uv locks,4 independent browser color/alpha/gradient measurement fixtures and6 ARM input-guard cases PASS.8 source documents and4 synthetic PNGs were anonymously fetched from the frozen commit and matched locally. |

The corrected baseline reproduced unnamed fields/checkboxes, missing primary headings, a focusable decorative chart, inaccessible scrolling and dialog/menu focus failures. Seven of the first eight dialogs failed keyboard handling. Expanded checks also reproduced invisible outlines, unannounced login errors, long transitions despite reduced motion, low light-theme text contrast, gradient-backed helper text near 1.00:1, a 2.25:1 focus outline,2.09:1 active More text and2.60:1 Delete text. Named native dialogs, connected invokers, labels/headings/skip link, alerts, keyboard menus and theme-specific colors address these concrete failures. The portaled action menu now has a named region. Delete normal/hover text must reach 4.5:1. API/authorization/VPN mutation behavior is unchanged.

The earlier source56 local “72 pages /1044 named actions” count is withdrawn as distinct-route evidence: its build omitted `VITE_URLPATH=panel` and redirected to Dashboard. Public PR76/release56 descriptions were corrected. The separate source56 CI/native/QR results and sealed security record remain valid within their stated scopes.

## Manual review and limits

The final228-scan report retains357 incomplete groups:217 contrast,128 symbolic close-name comparisons,8 empty-table associations and4 popup ID-reference reviews. These are not counted as automated passes. Original records remain available in CI artifacts; continuation reports include the scanner's explanations.

All 128 name comparisons point to symbolic × controls with functional Close/بستن names; this is intentional symbolic naming under [W3C Label in Name](https://www.w3.org/WAI/WCAG22/Understanding/label-in-name.html#symbolic-text-characters). The8 table groups refer to the synthetic empty operations audit table. For all 4 popup reviews, direct EN/FA/theme DOM checks confirm exactly one visible `mobile-more-menu` target for `aria-controls`; the scanner's original incomplete entries are retained. The4 separate manual focus results concern dark Node Archive gradients. Broader glass/gradient/chart contrast, screen-reader/speech-control/hardware behavior, forced colors and pixel-baseline certification remain unverified. Zero definite axe violations is not complete WCAG certification. [Focus contrast guidance](https://www.w3.org/WAI/WCAG22/understanding/non-text-contrast.html).

No empty VPS is available. Real public ACME issuance/renewal and a complete independent external node/client lifecycle remain NOT TESTED. Busy live services are not disposable fixtures. The original source45 security scan stays sealed with partial coverage and five historical findings fixed in46/50; this is not a new independent security audit. [Security closure](SECURITY-SCAN-CLOSURE.md).

Read-only Production health at 2026-10-17T15:57:45Z: local/public HTTP200/version55; protected panel/VPN/node/PostgreSQL process identities and restart counts, database counts/revision and environment/VPN hashes unchanged; no recent traceback/5xx. No Production mutation occurred. Any later health observation is recorded separately without relabeling this timestamp.

فارسی: نسخهٔ QA57 با آرشیو ثابت، CI دقیق، 228 اسکن خودکار و نصب عمومی شش مهمان بررسی شد. بازگشت دقیق فوکوس در136 بار باز و بسته‌شدن پنجره تأیید شد. موارد incomplete، بررسی دستی کنتراست و ابزارهای کمکی، ACME عمومی و VPS مستقل همچنان صریح‌اند؛ Stable اعلام نشده و سرویس زنده تغییر نکرده است.

[English illustrated guide](ACCESSIBILITY.md) · [راهنمای تصویری فارسی](ACCESSIBILITY.fa.md)
