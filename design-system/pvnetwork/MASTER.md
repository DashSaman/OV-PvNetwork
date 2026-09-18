# PVNetwork Panel — Master Design System

This is the product-wide UI source of truth for the admin panel and public subscription experience. Page-specific code may vary, but must not silently override these interaction/accessibility rules.

## Product character

- Operational VPN control plane: dense enough for administrators, calm enough for long sessions.
- Dark/light themes remain supported.
- Persian RTL and English LTR are first-class, not afterthoughts.
- Status-heavy UI must prioritize clarity over decorative effects.
- Never rely on color alone for state; combine text/icon/shape where needed.

## Layout tokens

- `--space-1: 4px`
- `--space-2: 8px`
- `--space-3: 12px`
- `--space-4: 16px`
- `--space-5: 20px`
- `--space-6: 24px`
- `--space-8: 32px`
- Desktop page padding: 24–30 px where space allows.
- Phone page padding: 12–16 px.
- Major card radius: 12–16 px; interactive controls: 8–12 px.

## Typography

- Body text target: 16 px for general forms/content; compact data rows may use 13–14 px when legible.
- Labels must not rely only on placeholders.
- Line height target: about 1.5 for body/help/error text.
- Long usernames, domains, UUID-like values and tokens must wrap safely or expose a full-value path.
- Identifiers that are easier to read LTR should use a local LTR treatment even inside RTL pages.

## Color and contrast

- Normal text target contrast: at least 4.5:1.
- Disabled controls remain understandable and should not look active.
- Success/warning/error/offline/maintenance states require a text/icon cue in addition to color.
- Light and dark mode tokens are defined centrally; components should avoid new raw hex values when an existing semantic token fits.

## Focus and keyboard

- Every keyboard-focusable control has a visible `:focus-visible` treatment.
- Do not remove outlines without an equally visible replacement.
- Icon-only buttons require accessible names.
- Dialogs/dropdowns must have appropriate semantic roles and state attributes.
- Opening an overlay moves focus into a useful location where practical; closing returns focus to the invoking control.
- Escape closes non-destructive overlays when safe and expected.

## Touch and pointer

- Primary interactive targets target at least 44×44 px where practical.
- Keep at least ~8 px separation between adjacent touch actions, especially destructive vs normal actions.
- No essential action may depend on hover.
- Busy/mutating actions disable or otherwise prevent duplicate submission until resolved.

## Navigation

- Desktop uses the sidebar hierarchy.
- Mobile must expose an equivalent route set; if the bottom bar cannot fit all routes, use a clear More/overflow destination rather than hiding features.
- Active location must be visually clear in RTL and LTR.
- Mobile fixed navigation must respect safe areas and not cover page actions/content.

## Tables and data density

At narrow widths choose deliberately:

1. Row-oriented management data → card/list transformation.
2. Mixed-priority data → priority columns + details disclosure.
3. Inherently tabular data → controlled table-only horizontal scrolling.

Actions cannot disappear simply because columns overflow. Search, sort and pagination must remain reachable above/below the data surface.

## Dialogs and drawers

- Width: `min(92vw, component max width)`.
- Height: bounded by the dynamic viewport (`100dvh`) with internal scrolling.
- On phones, prefer edge-safe spacing over decorative empty space.
- Primary/cancel actions remain reachable on short viewports.
- Destructive actions require explicit confirmation language.

## Forms

- Visible label for every field.
- Inline field error near the field; summary error may supplement but not replace it.
- Helper text is concise and persistent when it prevents mistakes.
- Numeric fields use sensible min/max/step and mobile-friendly input modes where possible.
- Required/optional state is programmatically understandable.
- Do not clear valid user input after a recoverable network error.

## Loading, empty, success and error states

Every major page/workflow should have:

- loading state without severe layout shift;
- empty state explaining what to do next;
- success feedback for completed mutation;
- actionable error text with Retry when retry is safe;
- timeout/partial-failure behavior for multi-node operations.

## Motion

- Motion communicates hierarchy/state, not decoration for its own sake.
- Respect `prefers-reduced-motion: reduce` by removing non-essential transitions/animations.
- Avoid layout-heavy width/height animations when transform/opacity works.
- Do not animate critical operational data so heavily that values are harder to read.

## Responsive matrix

Mandatory representative widths: 360, 375, 390, 430, 768, 1024, 1366, 1440 and 1920 px.

Core admin flows also verify 100%, 125% and 150% browser zoom.

## Page-specific priorities

- Dashboard: readable KPI cards and traffic/node health without cramped charts.
- Users: mobile-safe search/sort/pagination and always-reachable row actions.
- Nodes/Fleet: health/status/action affordances must survive narrow widths.
- Operations/Bandwidth: dangerous/canary/preview actions visually separated.
- Security: secrets are never exposed by default; token/TOTP actions have explicit labels.
- Backup/Restore: restore confirmation and progress are impossible to trigger accidentally.
- Subscription page: client choice, server recommendation, credentials and download instructions remain readable on phone first.

## Public documentation imagery

Documentation screenshots use demo/sanitized data only. Never capture live users, UUIDs, IPs, domains, keys, tokens, certificate material or internal capacities. For each release with meaningful visual changes, refresh both Persian and English guides with representative desktop/mobile views.

## Reference provenance

PVNetwork uses applicable principles from `nextlevelbuilder/ui-ux-pro-max-skill` as a design-quality reference, especially accessibility, touch interaction, responsive layout, resilient text, forms/feedback, navigation and reduced motion. PVNetwork's own Production-safety, privacy and workflow rules always take precedence.
