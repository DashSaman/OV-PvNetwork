# v1.0.61 validation — PVN-1045

Scope: actual subscription-route compatibility with pinned Starlette1.6.0, preserving schema, template content, assignment/download access and node probing semantics. Security60's aiohttp3.14.4 minimum/lock remain. No busy-node reinstallation, user mutation or Stable promotion is implied.

## Actual route red/green

Six tests register the real router/dependency and render the real template against synthetic SQLite. External node info is replaced at its slow boundary; CRUD/assignment/template/ASGI behavior stay real. The original code produces six identical unhashable-dict errors across rendering branches; missing-user and unassigned-download404 controls pass. A minimal explicit request/name/context correction passes all six tests. Cases cover healthy assigned nodes and download URLs, escaped hostile username/API-key exclusion, no nodes, unavailable nodes, disabled/draining/maintenance nodes without probing, missing user and denied unassigned downloads.

This focused Linux run uses a private isolated source snapshot and synthetic database, not a customer database. Live59 pointer and protected PIDs/restarts remain identical. Windows fcntl-dependent imports are not reported as passes. The full exact-source CI/Linux dependency/browser/privacy/build matrices, public native fixtures and authorized backup/canary/rollback/activation gates remain required.

## Changed workflow

Open an existing subscription URL: a valid user receives the HTML subscription page; available assigned nodes retain download links and unavailable nodes cannot gain a download link. Unknown users and unassigned downloads remain404. The page's design is unchanged; [English section guide](UI-GUIDE.md) and [راهنمای بخش‌ها](UI-GUIDE.fa.md) contain existing synthetic illustrations. Template-only responsive/QR/browser checks supplement the actual-route test; they do not replace it.

Final live checks must request an existing route locally/publicly, keep UUID/profile/password/body only in memory, verify readable HTML and identity/service continuity, and retain only sanitized results. External VPN-client, independent empty-VPS lifecycle, public ACME and real assistive hardware remain limits. [Original incident](incidents/2026-10-19-subscription-template-contract.md).
