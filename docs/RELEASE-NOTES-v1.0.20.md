# PVNetwork Panel v1.0.20 — Uniform language switching

`PVN-1005` makes every user-visible string follow the selected language across all 13 shipped languages.

## Problem
Switching the panel language left parts of the UI in the wrong language: 45 keys used through the translation function were missing from every language catalog, so i18next fell back to their hardcoded inline defaults — Persian defaults (reseller/unlimited-account labels, renewal modal, validations) appeared while English was selected, and English defaults (navigation labels, action buttons, copy feedback, sort menu) appeared while Arabic, Turkish, Chinese and other languages were selected. The Router/MikroTik modal was additionally fixed to RTL in every language.

## Fix
- All 45 missing keys are now cataloged and translated in all 13 languages (en, fa, ar, es, id, ja, pt_BR, ru, tr, uk, vi, zh_CN, zh_TW); every catalog now covers the full 463-key usage surface.
- The Router/MikroTik modal direction follows the active language through the `direction` key (`rtl` for Persian and Arabic, `ltr` elsewhere).
- The last two hardcoded English error messages in the download-from-node flows now use the catalog.

## Permanent gate
`tests/test_i18n_catalog_parity.py` scans every `t('key')` usage in the frontend source and requires each key to resolve (flat or nested) in every shipped language file, plus verifies the per-language `direction` value. A future feature that adds a key without translating it fails CI instead of shipping mixed languages.

The frontend bundle budget gate is 860000 bytes for this release: the fully-translated 13-language catalog grows the main chunk to 850.6 kB. `PVN-1004` registers on-demand language loading to shrink the chunk again.

## Scope and safety
UI-text only. No API contract, authentication, OpenVPN, Node, Router compatibility listener, profile or session behavior changes. Deployed as an atomic frontend asset switch; a backend restart is not required by this change itself.

## Release gate
Exact-head CI, verified rollback backup, atomic frontend deployment, local/public health and UI verification, sanitized artifact plus SHA256 publish and public re-download verification.
