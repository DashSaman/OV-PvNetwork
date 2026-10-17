# v1.0.56 verified QA — PVN-1040

Status: verified public QA. Exact CI, immutable artifact, anonymous download and public x86/ARM bootstrap gates PASS. No new Production deployment. Supported Stable remains v1.0.37; [final evidence and limits](VALIDATION-v1.0.56.md). The frozen source archive retains its initial pre-publication checkpoint.

## Change since v1.0.55

Fresh HTTPS installation previously enabled `certbot.timer` after webroot issuance without recording certificate activation on renewal. Updated certificate files could therefore leave Nginx serving its previous in-memory certificate. The actual issuance command now persists a fixed `--deploy-hook`: `nginx -t && systemctl reload nginx.service`. Certbot invokes this after successful issuance/renewal; a failed syntax check prevents reload. No restart, forced renewal or global hook directory change is introduced. Initial TLS/public health verification remains required.

The issue was reproduced against the actual issuance command before the fix. Its contract, two executable shell paths and real isolated Nginx certificate-swap test now pass in all six public x86/ARM distribution guests. The new certificate is served after safe reload with the same master PID; invalid syntax blocks reload. Public ACME issuance/renewal is still NOT TESTED without an authorized owned domain and eligible empty host. [Certbot's renewal documentation](https://eff-certbot.readthedocs.io/en/stable/using.html#renewing-certificates) describes persisted deploy hooks and their successful-renewal semantics.

## Upgrade and preservation

No schema, UI or VPN change. Version metadata advances together; existing illustrated v1.0.54 screenshots remain applicable. Native update/rollback instructions and verified backup requirements remain unchanged. Do not use fresh installation over an existing panel.

This hook is recorded for newly issued installer-managed lineages. Updating application code does **not** retrofit old or externally managed Certbot renewal configuration. Existing managed panels can use the scoped `sudo pvnetwork tls renew --yes --json` maintenance command after a verified backup: it selects one managed certificate, checks Nginx and gracefully reloads; it does not force issuance. Review automatic renewal of existing lineages separately in an authorized maintenance scope. No live certificate rotation, service change or Production deployment was performed for this task.

## Remaining Stable gates

Public ACME/external-VPS tests remain open. The original source45 security workbench is now completed/sealed with partial coverage; its five findings were fixed in46/50. See the [security closure](SECURITY-SCAN-CLOSURE.md). Exact v1.0.56 CI, immutable artifact, anonymous checksum and public x86/ARM bootstrap gates pass independently of the earlier v1.0.55 result. See [v1.0.56 evidence](VALIDATION-v1.0.56.md). Production deployment evidence remains [v1.0.55](VALIDATION-v1.0.55.md).
