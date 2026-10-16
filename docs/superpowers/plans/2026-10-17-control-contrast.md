# PVN-1035 / 1.0.51: form contrast

The existing light theme sets dark foreground tokens, while the later skin forces dark input backgrounds. Restore a coherent foreground/background pair for text inputs, select/options and textareas, including focus and placeholders. Reuse existing theme tokens and preserve geometry, event behavior and all existing languages. Keep dark panels and brand unchanged unless measured evidence requires a bounded adjustment.

1. Reproduce computed text/background contrast below 4.5:1 on the existing light-theme control; use a rendered/browser test, not a source-string assertion.
2. Apply the smallest shared CSS correction, then exercise actual populated controls and placeholder/option/focus contrast in EN/FA, both themes and native zoom across required widths.
3. Lint/build, adjacent critical workflows and frozen/public guards; refresh affected current Demo screenshots and bilingual release metadata. Publish no untested stable claim.

No Production permission is inferred. This is the existing release-readability requirement, not new product functionality.
