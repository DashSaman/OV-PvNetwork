# v1.0.47 candidate — PVN-1031

Quick edit now uses one stable form outside the users table's horizontal scroll
region. The editor fits the available content width, focuses the first editable
field on opening and retains an unsaved draft when resizing across the old
desktop/mobile breakpoint. Customer operations and authorization are unchanged.

On narrow layouts the brand and header actions occupy separate rows. Header
controls retain 44-pixel touch targets, the logout button has an accessible name,
and content leaves space for the fixed header. Admin/login logos are included in
the Vite asset graph instead of depending on a separate root-level asset route.

The browser regression uses Chromium's actual `tabs.setZoom`, verifies its zoom
value and CSS viewport, and passed all 108 EN/FA × dark/light × nine-width ×
100/125/150% zoom cases. Forty focused governance/UI tests and frontend lint/build
also passed locally.
It checks editor/header bounds, touch targets, keyboard focus/save, mouse save,
draft preservation across breakpoint changes, image loading, runtime page errors
and the reset/edit/status/assignment request sequence. The temporary extension
runs only in an owned disposable browser profile; it is not part of the app.

Synthetic Demo captures (no live panel/customer data):

| | Desktop | Mobile, scrolled editor |
|---|---|---|
| English | [Screenshot](images/pvn-1031/quick-edit-en-1440.png) | [Screenshot](images/pvn-1031/quick-edit-en-390.png) |
| Persian | [Screenshot](images/pvn-1031/quick-edit-fa-1440.png) | [Screenshot](images/pvn-1031/quick-edit-fa-390.png) |

This is a release candidate. Exact-commit CI, remaining whole-project language/UI
and native release checks, immutable public assets and scoped Production approval
remain separate gates. Public stable is 1.0.37; Production is 1.0.40.
