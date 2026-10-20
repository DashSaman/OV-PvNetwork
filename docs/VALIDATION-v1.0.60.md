# v1.0.60 validation — PVN-1046

## Verified public QA checkpoint, 2026-10-20

Frozen source `d83be2182222261a479733bbab8fbca3fc08adac`; archive SHA256 `6573c3da36bf056e853eae97397e3062750722913b51d282be00ec771a594e6f`, 90038619 bytes. [QA60 release](https://github.com/DashSaman/OV-PvNetwork/releases/tag/v1.0.60) and [merged PR82](https://github.com/DashSaman/OV-PvNetwork/pull/82) retain this exact source; the merge tree matches the tested tree.

| Gate | Actual result |
| --- | --- |
| Exact source | All eight checks PASS: [push](https://github.com/DashSaman/OV-PvNetwork/actions/runs/39304286535), [PR](https://github.com/DashSaman/OV-PvNetwork/actions/runs/39304371629) |
| Immutable tag | All four [tag checks](https://github.com/DashSaman/OV-PvNetwork/actions/runs/39412121444) PASS |
| Linux regression | 733 unit/governance tests, 80 explicit skips; 82 root, 38 security, 37 router tests, one external SSH skip; isolated real VPN controls PASS |
| Dependency and Web Push | Both frozen panel/node audits PASS in each validation job; fresh-cache audit PASS; eight dispatch and five actual encryption/VAPID/guarded transport tests PASS |
| Browser/accessibility | 272 rendered states, 228 axe scans, 136 dialogs, 144 focus measurements, QR24 and subscription8 PASS; 16 manual rendered classifications and 357 incomplete axe results remain explicit |
| Public native installation | All six fresh/repeat guests PASS: [x86](https://github.com/DashSaman/OV-PvNetwork/actions/runs/39413348048), [real ARM64](https://github.com/DashSaman/OV-PvNetwork/actions/runs/39413351046); Ubuntu22.04/24.04 and Debian12, exact source/hash, systemd/proxy/assets/SQLite/private permissions/CLI and repeated environment/DB/PID preservation |
| Anonymous download | Complete 90038619-byte archive and checksum PASS |
| Production | NOT DEPLOYED. Live remains59; the owner confirmed concurrent server work is ongoing. No final60 backup, candidate activation or restart has been started |

The read-only preflight refused the unrelated active transient-service gate before backup or activation. Its expiry does not authorize proceeding. After the owner reports completion, repeat preflight and create a fresh native application/database backup with actual restore verification, record retained59 rollback, then run canary and the authorized narrow activation. Installed dependency, local/public health, complete customer identities, keys/configuration, cached profiles and protected services must pass before this task can close. No previous backup or passing public fixture substitutes for these live gates.

فارسی: کد، tag، دانلود کامل ناشناس و هر شش نصب عمومی نسخهٔ60 تأیید شده‌اند. پنل هنوز59 است؛ مالک ادامهٔ کار هم‌زمان را تأیید کرده و بکاپ نهایی/استقرار60 شروع نشده است. پس از اعلام پایان آن کار، بکاپ تازه با بازیابی واقعی، rollback، canary و کنترل سرویس‌ها و اطلاعات کاربران لازم‌اند.

## Original scope and candidate evidence

Scope: remove the known affected aiohttp3.14.3 dependency from the frozen panel artifact, enforce a patched minimum and preserve guarded Web Push behavior. Package presence is confirmed; an application-specific remote resource-exhaustion exploit is not claimed. Native node dependencies, data schema, SSH/VPN/authorization and UI behavior are unchanged.

Original frozen audit: FAIL, three entries (CVE-2026-111064, GHSA-2g87-pp6c-29x5, CVE-2026-111063), all reporting fixed3.14.4. Existing real Web Push encryption/transport tests: five PASS before the update. Windows dispatch import requires Linux fcntl and is explicitly not a local pass; full Linux CI is required.

Candidate gates: fresh corrected frozen audit; legitimate real encryption/VAPID/guarded session and dispatch checks; challenge stale locks; syntax/locks/build; full exact-head CI and native fresh/repeat; immutable public assets and x86/ARM public bootstrap; fresh recoverable backup/actual restore; isolated canary; retained59 rollback; installed package version plus health/data/service/profile continuity. Pending results must not be inferred as successful.

No UI change is introduced. Existing synthetic [node guide](NODE-VALIDATION-v1.0.59.md) and [Persian guide](NODE-VALIDATION-v1.0.59.fa.md) illustrate the unchanged workflow. Independent empty-VPS/client, public ACME, real assistive hardware and partial source45 security-scan limits remain. Subscription PVN-1045 is queued separately for61.

[Original dependency incident](incidents/2026-10-19-dependency-audit-aiohttp.md) · [Upstream affected/patched advisory](https://github.com/aio-libs/aiohttp/security/advisories/GHSA-2g87-pp6c-29x5).

## Local candidate checkpoint

Fresh panel and native-node frozen-export audits PASS with no known vulnerabilities reported; original59 export FAIL remains retained. An alternate stale3.14.3 lock is rejected by the patched manifest's offline `--check`; offline resolution chooses3.14.4. Only aiohttp and panel metadata change in the root lock; unrelated package records and all native-node dependency records are identical.

Five real encryption/VAPID/transport controls plus18 portable rename/brand/version contracts PASS (23 total). Backend compile, Bandit medium/high gate, frontend production build, frozen offline lock and six-document/145-local-link/privacy checks PASS. An initial Windows test command lacked UTF-8 mode and failed four file decodes; the corrected `python -X utf8` invocation passes all23 without source changes. At this earlier local checkpoint Linux fcntl-dependent dispatch/settings and exact-source CI were still required; the verified Linux results above supersede that pending state. No pass is inferred from Windows imports.
