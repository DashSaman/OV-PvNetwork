# v1.0.51 candidate — PVN-1035

The light theme supplied dark text while the later skin forced dark input wells. In an actual browser the old input contrast was only 1.13–2.16:1 across even the extreme possible backgrounds. Values could be difficult to read in user, node and security forms.

The common input/select/textarea surface now uses the same existing theme as its foreground, including focus and option rows. Placeholders have explicit colors and full opacity. No dimensions, API behavior, account data or translations change.

Rendered regression checks populated fields, selects/textareas, placeholders and focused controls in Users, Nodes including its creation dialog, Security, Monitoring and Bandwidth. The old build failed; the corrected build passed 108 EN/FA × themes × nine widths × native 100/125/150% zoom combinations, 7,128 control observations at a 4.5:1 floor. Fully transparent header controls are outside this form-value contrast test. This is not whole-page WCAG certification. Twenty relevant Linux contracts and lint/build passed. Adjacent interaction/final CI and immutable-artifact gates are recorded separately.

[Current Demo](CURRENT-DEMO.md) uses synthetic data. No database migration or service restart is required for this CSS change itself. Code rollback restores the old low-contrast colors. Publication and separately scoped Production authorization remain open.

Adjacent quick-edit interaction regression: all 108 language/theme/width/native-zoom cases PASS.

The same Demo review found dark light-theme view titles over retained dark gradients (1.01–2.70 contrast bounds). The shared title color is now light in either theme; a separate four-case EN/FA/theme browser check covers gradient endpoints against extreme underlying backgrounds at the 3:1 large-bold-text floor. The form-value 108-case evidence above predates only this title-color addition.
