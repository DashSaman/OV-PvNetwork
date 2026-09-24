# PVNetwork Panel v1.0.21 — Full language uniformity

`PVN-1006` completes the language-switching fix: every user-visible string now follows the selected language in all 13 shipped languages.

## What was still wrong after v1.0.20
- 28 catalog keys had Persian values inside the English catalog (and copied into the other 11 non-Persian catalogs): backup/security save labels, transfer dialogs, 2FA prompts, quota labels and more showed Persian under English and every other non-Persian language.
- The Backup/Restore panel, the AnyConnect user modal, the reseller-deletion dialogs and several form hints were entirely hardcoded Persian with no translation calls — they stayed Persian in every language.
- The Backup panel forced RTL layout and Persian-formatted timestamps regardless of language.

## What changed
- The 28 polluted values now carry real translations in every non-Persian catalog; the Arabic catalog keeps proper Arabic (verified free of Persian-only characters).
- About 100 previously hardcoded strings across 7 components now use the translation system with new catalog keys; 563 used keys resolve in all 13 languages.
- The Backup panel direction and timestamp locale follow the active language.
- Permanent CI gates: non-Persian catalogs must contain zero Arabic-script values (native language names exempt), the Arabic catalog must contain zero Persian-only characters, and no component may contain raw Persian text outside translation calls.

## Bundle
The fully translated 13-language catalog grows the main chunk to 942.4 kB; the CI budget is 950000 bytes for this release. `PVN-1004` (on-demand language loading) remains the registered path to shrink it.

## Scope and safety
UI-text only. No API, authentication, OpenVPN, Node, Router listener, profile or session behavior changes.

## Release gate
Exact-head CI, atomic frontend deployment, local/public health verification, sanitized artifact plus SHA256 publish and public re-download verification.
