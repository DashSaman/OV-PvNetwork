# v1.0.57 accessibility validation — PVN-1041

Status: **candidate; exact-source Linux CI and publication pending**. Supported Stable remains v1.0.37. The live panel remains v1.0.55. This task performs no Production deployment, restart, certificate, database, node, routing or firewall mutation.

## Reproduced defects and corrections

The correctly built baseline reproduced unnamed fields/checkboxes, missing primary headings, a focusable decorative chart, unreachable scroll regions, skipped heading levels and dialog focus/Escape failures. Seven of the first eight dialog flows failed keyboard containment or dismissal. Expanded tests also reproduced missing menu navigation, an invisible outline, unannounced login errors, long transitions despite reduced-motion preference and light-theme contrast failures (4.34–4.38:1 secondary text; translucent navigation as low as1.03:1). The real Jinja subscription reproduced missing main landmark, keyboard-inaccessible command scrolling and QR initial-focus failure.

The patch adds a shared native dialog wrapper, explicit boundary focus handling, connected invokers, associated labels, alert semantics, translated primary headings/skip link, keyboard menus, visible outlines, stronger reduced-motion rules and corrected theme surfaces. Subscription QR retains escaped inert data and fixed listeners; native modality now contains focus and returns it on close. No backend authorization, API, VPN or node mutation logic changes. React runtime splitting keeps the largest bundle below the existing990,000-byte limit; the limit is not raised.

## Evidence and reproducibility

- Fresh local quiet lint, production build and runtime npm audit PASS (zero reported vulnerabilities). Thirty-nine portable governance/version/template/brand tests PASS, zero skips; both frozen uv locks validate offline. Linux-dependent API/runtime tests remain CI coverage; Windows lacks `fcntl` and is not counted as passing those tests.
- `frontend/tests/accessibility-smoke.mjs`: all nine actual admin routes plus unauthenticated login, EN/FA, light/dark,390/1440px; seventeen distinct dialogs, real keyboard navigation/focus/escape, visible focus, alert semantics and reduced motion. Exact URL assertions reject a build that silently redirects to Dashboard. A deliberately unnamed negative-control input must fail axe.
- `frontend/tests/subscription-accessibility.mjs`: real Jinja rendering, eight EN/FA/theme/width combinations, page and open QR scans, focus containment/return. Local result:8 cases, zero reported violations,16 incomplete result groups retained for manual review.
- Final admin matrix PASS:80 page views,136 opened dialogs,216 axe scans, zero reported violations, one deliberately failing negative control.341 incomplete result groups remain recorded:205 contrast,128 symbolic close-name comparisons and8 empty-table associations. None is counted as a pass.
- Real browser zoom keyboard matrix PASS:108 EN/FA × theme × nine-width ×100/125/150% combinations,216 page views and432 dialog openings across add/edit user, edit node and settings confirmation. After the final light surface correction, all54 light-theme combinations repeat PASS (108 page views/216 openings). Exact widths:360,375,390,430,768,1024,1366,1440,1920. These keyboard checks do not add another axe pass count.
- Visual review exposed gradient-backed light-theme helper text near1.00:1 that axe left incomplete. A separate endpoint contrast regression reproduced it. After pairing the modal surface, labels and helper text with the light palette, focused EN27/FA12 scans and the final full matrix pass without violations. Four synthetic EN/FA desktop/mobile focus images were refreshed and visually reviewed.
- CI runs existing browser/security/native tests plus both new axe gates. JSON artifacts retain failures and incomplete items. External requests are blocked; API responses and all screenshots are synthetic loopback fixtures.

The extra local source56 “72 pages /1044 named actions” report was invalid as distinct-route evidence: that local build lacked `VITE_URLPATH=panel`, so navigation redirected to Dashboard. It is withdrawn. The new gate asserts route identity before testing, and login explicitly clears authentication. This does not invalidate the separate source56 CI, native installation, QR or sealed security evidence.

## Manual review and remaining gates

Automated zero violations does not imply complete WCAG compliance. Glass/gradient/opacity/chart rendering can leave contrast incomplete; symbolic close labels and empty-table associations may also need manual interpretation. Record the exact incomplete counts/rules with the final matrix. Full screen-reader behavior, hardware/touch assistive technology, forced-colors and pixel-baseline certification remain unverified. These are independent of the completed partial source45 security scan.

No empty VPS is available. Public ACME issuance/renewal and a complete separate external node/client lifecycle remain NOT TESTED. Busy live services are not test fixtures. New57 exact CI, immutable assets/public bootstrap and any separately authorized Production activation remain gates; historical56 results are not relabeled as57 passes.

[English illustrated keyboard guide](ACCESSIBILITY.md) · [راهنمای تصویری فارسی](ACCESSIBILITY.fa.md) · [sealed security scope](SECURITY-SCAN-CLOSURE.md)

Read-only Production health at `2026-10-17T15:57:45Z`: local/public HTTP200/version55, panel/VPN/node/PostgreSQL active, protected process identities and restart counts unchanged; database counts/revision and environment/VPN configuration hashes match the prior check. No recent traceback/5xx lines. No Production mutation occurred.
