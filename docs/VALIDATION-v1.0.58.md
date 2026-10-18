# Public QA v1.0.58 validation — PVN-1042

Status: **verified public QA and owner-authorized panel deployment; remaining manual/infrastructure gates stay open**. Supported Stable remains v1.0.37; the authorized live panel now runs v1.0.58. [Production evidence](PRODUCTION-v1.0.58.md). The separate authorized node recovery is recorded under [PVN-1043](incidents/2026-10-18-node-address-change.md); it is not a UI deployment.

## Immutable identity and public installation

| Item | Verified value |
| --- | --- |
| Release | [v1.0.58 public QA](https://github.com/DashSaman/OV-PvNetwork/releases/tag/v1.0.58), prerelease, not latest Stable |
| Frozen runtime source | `2c6ee6e9b8894125659d87a4bfd99817870a0440` |
| Archive | `pvnetwork-panel-v1.0.58.tar.gz`, 89828636 bytes |
| SHA256 | `cff93a239dac5f2b147a1397eb019af6473b68a26dc43d99cb6cc67f0b1d3a60` |
| Exact-source CI | [push 39143625883](https://github.com/DashSaman/OV-PvNetwork/actions/runs/39143625883), [PR 39143629123](https://github.com/DashSaman/OV-PvNetwork/actions/runs/39143629123), all 8 jobs PASS |
| Official public x86 bootstrap | [39145943181](https://github.com/DashSaman/OV-PvNetwork/actions/runs/39145943181), all 3 distribution guests PASS; unrelated validate job intentionally skipped |
| Official public native ARM bootstrap | [39145949018](https://github.com/DashSaman/OV-PvNetwork/actions/runs/39145949018), all 3 guests PASS, actual `aarch64` runner/`arm64` guest receipts |

The archive/checksum were downloaded anonymously and the full archive hash/size matched. Each public native job independently verifies the public artifact before execution. All six Ubuntu 22.04, Ubuntu 24.04 and Debian 12 guests report fresh installation PASS, repeat-install environment/database/PID preservation PASS, systemd/proxy/UI assets/SQLite/private permissions PASS and installed CLI PASS, with `public_bootstrap:true` and the exact hash above. [Machine-readable receipts](evidence/v1.0.58-public-native.json) retain job IDs and architecture evidence. These are isolated systemd containers in Setup Mode, not independent external VPS or public ACME results.

The tag/assets are immutable. The frozen archive's included docs describe its prepublication checkpoint; this later documentation-only record and the release page add the actual remote results. Integration documentation does not redefine the frozen runtime source.

## Browser and regression evidence

The release fixes confirmed rendered-contrast failures in light navigation/dashboard/node-health/backup surfaces, chart/helper text, form boundaries and the mobile header while scrolling. The deployment console uses the existing native modal mechanism, with log/progress/error semantics, focus containment/return and SSH-secret clearing after successful or rejected submission. An observed SSH fingerprint is never automatically accepted.

- Both exact-source validate jobs run 733 unit/governance tests successfully with 80 explicit skips, plus 82 separate root fixtures, 38 security tests and 37 router tests with one external-SSH skip. Isolated actual OpenVPN dual-auth handshakes, dependency audits, lint, build and privacy guards pass. Largest JavaScript asset is 800629 bytes against a 990000-byte budget. Skips are not passes.
- The route/dialog gate passes 80 pages, 136 dialog openings, 228 axe scans, 144 measured focus outlines and its failing negative control, with zero definite violations. All 357 original incomplete groups remain recorded; they are not automated passes. Subscription accessibility passes 8 cases with 16 incomplete groups retained.
- CI rendered review passes 272 states, 8502 painted-text observations, 840 control boundaries, 48 opaque file-control color pairs, 8 gradient focus samples and 8 conservative gradient text bounds, with zero failures. Twelve positive/negative fixtures cover alpha/pseudo layers, borders/fills, clipping, gradients and file-control colors. Sixteen manual classifications remain: 8 gradients with separate conservative bounds and 8 native file-control paintings. Empty textboxes are not painted text. A 12-state file-focused check passes before the full matrix.
- Final Windows Chromium rendered review passes 272 states, 8494 text observations, 830 boundaries, 48 file-control pairs and the same gradient/fixture counts. Eight actual file-control captures across EN/FA, both themes and 390/1440px were visually reviewed for readable filename/button text and boundaries. This does not certify OS file-picker behavior, Linux native painting or assistive hardware.
- A synthetic real-browser regression reproduced the missing named deployment dialog before the fix. CI then passes 12 normal-color, 12 forced-color-emulation and 4 actual Chromium 400% zoom/text-spacing deployment cases. Each covers running, job failure, HTTP rejection, retry, success, exact invoker return and credential clearing. Browser AX trees verify native dialog/log exposure; this is not a screen-reader session.
- The assistive-display gate passes 8 forced-color/browser-AX cases and 36 actual 400%-zoom/text-spacing route cases. The public control-contrast helper passes 4 good/bad solid/gradient fixtures and 308 measurements. The private local expanded native 100/125/150% matrix passes 108 cases / 8316 control measurements. A separate local deployment harness passes 108 combinations across EN/FA/themes/nine widths/native 100/125/150% zoom. Local 108 cases are not claimed as 108 CI cases.
- Local build, quiet lint, 20 portable tests, both offline frozen-lock checks, bilingual documentation/link checks and synthetic screenshots pass. Windows cannot import POSIX-only `fcntl` contracts; the Linux CI results provide that coverage.

The earlier e703c91 checkpoint passed six native guests and unit/audit/build gates, then exposed a helper assumption that every heading background must be a gradient. Its test-only correction preserves contrast/alpha thresholds. The ec2c3fa checkpoint passed that correction and 228 axe scans, then exposed two Linux empty native-file raster samples. Separating native pseudo-control colors from an empty ordinary text value, explicit theme colors and the early file gate address those samples. Earlier failed reports remain evidence, not relabeled passes; neither private superseded archive was published. No axe rule or contrast threshold was disabled.

## Authorized Production activation

On 2026-10-18, the exact frozen public archive was staged and verified on the authorized panel. Native PostgreSQL backup/restore rehearsal, cloned candidate, compatible retained 55 rollback readiness, local/public health/assets/API, private cached-profile continuity and protected identities/services passed. The observed panel maintenance span was 129.07 seconds. No node reinstallation, VPN/tunnel restart, credential rotation or stale database restore occurred. [Detailed scope](PRODUCTION-v1.0.58.md).

Actual live-browser form checks pass 4 EN/FA/theme/mobile/tablet/desktop cases. Each submits a reserved documentation address and invalid SSH port 0; the real backend returns 422 for that field before a job handler runs. Native dialog/log/alert semantics, associated host-trust help, exact keyboard return and SSH-secret clearing pass. This is a scoped UI/validation result, not a complete node installation. Visual review found inherited `[object Object]` text for structured validation arrays; PVN-1044 stays open for the next immutable patch. No existing node is used as a fresh-install fixture.

## Remaining gates

Original QA57 incomplete entries remain in its [immutable validation record](VALIDATION-v1.0.57.md). These scoped browser/visual checks do not establish complete WCAG conformance. Actual screen-reader/speech/OS hardware review, public ACME issuance/renewal, an independent external fresh-node/client lifecycle and the inherited structured-validation message follow-up remain open. The owner-authorized panel activation is verified separately. No empty VPS is available; busy live nodes are not disposable fixtures. The [sealed source45 security scan](SECURITY-SCAN-CLOSURE.md) remains partial; this is not a new independent security scan. No full Stable promotion or external VPN-client result is inferred from panel health or native container installation.

[English illustrated guide](MANUAL-ACCESSIBILITY-v1.0.58.md) · [راهنمای تصویری فارسی](MANUAL-ACCESSIBILITY-v1.0.58.fa.md)
