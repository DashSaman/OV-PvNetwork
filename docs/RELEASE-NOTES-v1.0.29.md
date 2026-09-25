# PVNetwork Panel v1.0.29 — Installable panel (PWA) + mobile users-table cards

`PVN-1013`.

## Installable admin panel
- A web app manifest (`manifest.webmanifest`) with icons and `display: standalone` is now part of the built panel.
- "Add to Home Screen" on Android/iOS and "Install App" in desktop browsers give PVNetwork its own window and icon, launched straight into the panel path.
- No service worker was added on purpose: the panel requires an online backend, and skipping it avoids cache-staleness incidents on production updates while still allowing installation.

## Mobile users-table cards
- On phones (≤640px) the Users table transforms into one stacked card per user: every field on its own line, actions at the bottom — no more horizontal scrolling.
- Larger screens keep the full table unchanged. This lands the Users screen first; the remaining management screens follow the same pattern under the existing PVN-124..133 items.

## Scope and safety
Frontend-only (manifest, icon, index link, scoped CSS). No API, auth, database, OpenVPN, Node or Router changes; deployment is an atomic frontend asset switch.

## Release gate
Exact-head CI (including the 9-width responsive matrix), focused contract tests, atomic frontend deployment with public verification, sanitized artifact plus SHA256 publish and public re-download verification.
