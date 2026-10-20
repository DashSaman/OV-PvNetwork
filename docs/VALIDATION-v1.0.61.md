# v1.0.61 validation — PVN-1045

## Final public QA checkpoint, 2026-10-20

Frozen source `58722e71dd0ccec9d900d6da2157ac32bca92bf6`; archive SHA256 `b2572d9888fd166b8aabb5b2c4521ee39ed8a57251365c6a8413c5d542ce7710`, 90041576 bytes. All eight exact-source checks PASS: [push](https://github.com/DashSaman/OV-PvNetwork/actions/runs/39412204464) and [PR](https://github.com/DashSaman/OV-PvNetwork/actions/runs/39412324734). [PR83](https://github.com/DashSaman/OV-PvNetwork/pull/83) is merged; its merge tree equals the frozen tested tree.

Both validation logs confirm all six actual subscription-route regressions pass, 739 unit/governance tests with80 explicit skips,82 root,38 security and37 router tests with one external SSH skip, both frozen dependency audits, build and full browser/accessibility checks. The source native fixtures pass on all three supported distributions. Browser totals include272 rendered states,228 axe scans,136 dialogs,144 focus measurements, QR24 and subscription8; manual/incomplete classifications remain, including357 incomplete axe results. These source results do not establish anonymous public bootstrap or Production deployment.

### Public artifact checkpoint

[QA61 release](https://github.com/DashSaman/OV-PvNetwork/releases/tag/v1.0.61) is published with immutable source/tag/assets. The complete90041576-byte anonymous download and checksum PASS. All six exact-source public fresh/repeat guests PASS: [x86](https://github.com/DashSaman/OV-PvNetwork/actions/runs/39416053666) and [real ARM64](https://github.com/DashSaman/OV-PvNetwork/actions/runs/39416055962), Ubuntu22.04/24.04 and Debian12. Each actual guest receipt confirms version1.0.61/hash, public bootstrap, systemd/proxy/UI assets/SQLite/private permissions/CLI and preservation of environment/database/PIDs on repeat. All three ARM logs verify runner aarch64/guest arm64 and the exact frozen source.

All four additional [tag CI checks](https://github.com/DashSaman/OV-PvNetwork/actions/runs/39415285325) now PASS. The complete tag validation log confirms739 unit/governance tests with80 explicit skips,82 root,38 security,37 router, both dependency audits, all six actual subscription-route regressions and the full browser/accessibility gates. This confirms all12 source/tag checks; no pass is inferred from another workflow. Final local package verification also confirms the expected SHA256/size,1093 safe archive members,11 critical files identical to the frozen Git source and27 executable scripts with LF endings. Published tag/assets remain unchanged.

Production remains59. The owner confirmed concurrent server work is still ongoing; no final61 backup, activation or restart has started. After that work ends, security60 must activate and pass first, followed by a separate fresh61 native backup/actual restore, retained60 rollback, canary, narrow activation and local/public real-route validation. Both tasks remain open until actual live evidence exists.

فارسی: هر هشت بررسی کد دقیق و شش تست واقعی مسیر اشتراک پاس شدند و PR83 با همان درخت تست‌شده ادغام شد. این نتیجه به معنی استقرار نیست؛ پنل هنوز59 است و تا اعلام پایان کار هم‌زمان، بکاپ نهایی و استقرار شروع نمی‌شود.

دانلود کامل ناشناس، هر شش نصب عمومی61 و هر چهار بررسی تکمیلی CI روی tag نیز پاس شدند. این تأیید QA است؛ شرط‌های بکاپ/بازیابی واقعی، rollback، استقرار و بررسی پنل زنده پس از پایان کار هم‌زمان همچنان باقی‌اند.

## Original scope and route reproduction

Scope: actual subscription-route compatibility with pinned Starlette1.6.0, preserving schema, template content, assignment/download access and node probing semantics. Security60's aiohttp3.14.4 minimum/lock remain. No busy-node reinstallation, user mutation or Stable promotion is implied.

## Actual route red/green

Six tests register the real router/dependency and render the real template against synthetic SQLite. External node info is replaced at its slow boundary; CRUD/assignment/template/ASGI behavior stay real. The original code produces six identical unhashable-dict errors across rendering branches; missing-user and unassigned-download404 controls pass. A minimal explicit request/name/context correction passes all six tests. Cases cover healthy assigned nodes and download URLs, escaped hostile username/API-key exclusion, no nodes, unavailable nodes, disabled/draining/maintenance nodes without probing, missing user and denied unassigned downloads.

This focused Linux run uses a private isolated source snapshot and synthetic database, not a customer database. Live59 pointer and protected PIDs/restarts remain identical. Windows fcntl-dependent imports are not reported as passes. At this earlier reproduction checkpoint full exact-source CI/Linux dependency/browser/privacy/build matrices were pending; the verified source checkpoint above supersedes that state. Public native and live backup/canary/rollback/activation results are recorded separately.

## Changed workflow

Open an existing subscription URL: a valid user receives the HTML subscription page; available assigned nodes retain download links and unavailable nodes cannot gain a download link. Unknown users and unassigned downloads remain404. The page's design is unchanged; [English section guide](UI-GUIDE.md) and [راهنمای بخش‌ها](UI-GUIDE.fa.md) contain existing synthetic illustrations. Template-only responsive/QR/browser checks supplement the actual-route test; they do not replace it.

Final live checks must request an existing route locally/publicly, keep UUID/profile/password/body only in memory, verify readable HTML and identity/service continuity, and retain only sanitized results. External VPN-client, independent empty-VPS lifecycle, public ACME and real assistive hardware remain limits. [Original incident](incidents/2026-10-19-subscription-template-contract.md).
