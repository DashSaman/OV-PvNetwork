# v1.0.50 candidate — PVN-1034

A node label could enter a quoted inline QR event handler after HTML entity decoding. A scoped node-writing actor with a reachable node could persist a label that executes script when a visitor activates that node's subscription QR. The synthetic regression demonstrated a harmless marker; no live exploitation or credential access was performed.

The template now stores autoescaped labels and download URLs in data attributes. Fixed listeners read those strings and call the existing QR implementation. The caption/title continue using text content. No node identity, profile, quota or database schema changes.

The old-source HTML/parser and browser probes reproduced the issue. Eight focused QR tests passed. The real Jinja-to-browser regression passed 24 EN/FA, dark/light, desktop/phone and native 100/125/150% zoom cases, each using mouse, Enter and Space, checking the exact payload, real vendored QR SVG and Escape. The 108-case quick-edit matrix passed on this build. Full Linux: 712 tests, 706 passes, six PostgreSQL-only skips. Frontend lint/build passed. PostgreSQL behavior is unchanged from v1.0.48's six actual PostgreSQL cases.

All 13 existing languages are retained. A separate 6,318-view navigation/layout sweep passed on v1.0.47 across all languages, themes, nine widths and native zoom; its manual reproducer is included. This is layout evidence, not certification of every translation or assistive technology.

[Current Demo screenshots](CURRENT-DEMO.md) use only synthetic data. Exact-head CI, final immutable-artifact validation, full mission, publication and scoped Production authorization remain gates. Code rollback restores the earlier vulnerable handler; do not treat that as a secure long-term state.
