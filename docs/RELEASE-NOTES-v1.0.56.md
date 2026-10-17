# v1.0.56 QA candidate — PVN-1040

Status: unpublished candidate; exact CI, immutable artifact/public bootstrap and applicable release gates remain pending. Public stable remains v1.0.37 and the authorized live panel remains v1.0.55.

## Change since v1.0.55

Fresh HTTPS installation previously enabled `certbot.timer` after webroot issuance without recording certificate activation on renewal. Updated certificate files could therefore leave Nginx serving its previous in-memory certificate. The actual issuance command now persists a fixed `--deploy-hook`: `nginx -t && systemctl reload nginx.service`. Certbot invokes this after successful issuance/renewal; a failed syntax check prevents reload. No restart, forced renewal or global hook directory change is introduced. Initial TLS/public health verification remains required.

The issue was reproduced against the actual issuance command before the fix. Its contract passes locally afterward; two executable shell paths and a real isolated Nginx certificate-swap test require Linux CI. The native harness requires the fixture tools, so those checks cannot silently skip. Public ACME issuance/renewal is still NOT TESTED without an authorized owned domain and eligible empty host. [Certbot's renewal documentation](https://eff-certbot.readthedocs.io/en/stable/using.html#renewing-certificates) describes persisted deploy hooks and their successful-renewal semantics.

## Upgrade and preservation

No schema, UI or VPN change. Version metadata advances together; existing illustrated v1.0.54 screenshots remain applicable. Native update/rollback instructions and verified backup requirements remain unchanged. Do not use fresh installation over an existing panel.

This hook is recorded for newly issued installer-managed lineages. Updating application code does **not** retrofit old or externally managed Certbot renewal configuration. Existing managed panels can use the scoped `sudo pvnetwork tls renew --yes --json` maintenance command after a verified backup: it selects one managed certificate, checks Nginx and gracefully reloads; it does not force issuance. Review automatic renewal of existing lineages separately in an authorized maintenance scope. No live certificate rotation, service change or Production deployment was performed for this task.

## Remaining Stable gates

Public ACME/external-VPS tests, the partial original security workbench and the exact new-release gates remain explicit. Native ARM64 public installation of immutable v1.0.55 passed all three supported distributions; that result is not automatically evidence for changed v1.0.56 bytes. See [v1.0.55 evidence](VALIDATION-v1.0.55.md).
