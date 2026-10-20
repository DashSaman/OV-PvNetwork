# v1.0.60 validation — PVN-1046

Scope: remove the known affected aiohttp3.14.3 dependency from the frozen panel artifact, enforce a patched minimum and preserve guarded Web Push behavior. Package presence is confirmed; an application-specific remote resource-exhaustion exploit is not claimed. Native node dependencies, data schema, SSH/VPN/authorization and UI behavior are unchanged.

Original frozen audit: FAIL, three entries (CVE-2026-111064, GHSA-2g87-pp6c-29x5, CVE-2026-111063), all reporting fixed3.14.4. Existing real Web Push encryption/transport tests: five PASS before the update. Windows dispatch import requires Linux fcntl and is explicitly not a local pass; full Linux CI is required.

Candidate gates: fresh corrected frozen audit; legitimate real encryption/VAPID/guarded session and dispatch checks; challenge stale locks; syntax/locks/build; full exact-head CI and native fresh/repeat; immutable public assets and x86/ARM public bootstrap; fresh recoverable backup/actual restore; isolated canary; retained59 rollback; installed package version plus health/data/service/profile continuity. Pending results must not be inferred as successful.

No UI change is introduced. Existing synthetic [node guide](NODE-VALIDATION-v1.0.59.md) and [Persian guide](NODE-VALIDATION-v1.0.59.fa.md) illustrate the unchanged workflow. Independent empty-VPS/client, public ACME, real assistive hardware and partial source45 security-scan limits remain. Subscription PVN-1045 is queued separately for61.

[Original dependency incident](incidents/2026-10-19-dependency-audit-aiohttp.md) · [Upstream affected/patched advisory](https://github.com/aio-libs/aiohttp/security/advisories/GHSA-2g87-pp6c-29x5).

## Local candidate checkpoint

Fresh panel and native-node frozen-export audits PASS with no known vulnerabilities reported; original59 export FAIL remains retained. An alternate stale3.14.3 lock is rejected by the patched manifest's offline `--check`; offline resolution chooses3.14.4. Only aiohttp and panel metadata change in the root lock; unrelated package records and all native-node dependency records are identical.

Five real encryption/VAPID/transport controls plus18 portable rename/brand/version contracts PASS (23 total). Backend compile, Bandit medium/high gate, frontend production build, frozen offline lock and six-document/145-local-link/privacy checks PASS. An initial Windows test command lacked UTF-8 mode and failed four file decodes; the corrected `python -X utf8` invocation passes all23 without source changes. Linux fcntl-dependent dispatch/settings and complete exact-source CI remain required; no pass is inferred from Windows imports.
