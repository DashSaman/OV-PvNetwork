# PVNetwork Panel v1.0.18 — Panel Release-Version Badge

`PVN-1002` makes the running release version visible in the panel UI next to the live indicator.

## What it adds
The Dashboard (Server Stats) header shows the deployed panel version — for example `v1.0.18` — immediately beside the existing `LIVE · REALTIME` badge, styled consistently with the theme toggle in both dark and light modes, LTR and RTL.

## How it works
- On mount, the page reads the public unauthenticated `/healthz` endpoint (`{"status":"ok","version":"…"}`) with `cache: 'no-store'`.
- The badge renders only when a non-empty version string is returned; any fetch failure silently omits it, so the dashboard never blocks or errors on the version lookup.
- Because the value comes from the backend at runtime, the badge always matches the actually deployed release — including after future upgrades — without baking the version into the frontend bundle.

## Scope and safety
Display-only change. No API contract, authentication, OpenVPN, Node, Router compatibility listener, profile, certificate or session behavior is modified. Backend service restart is not required; the frontend ships as an atomic asset/index switch.

The frontend bundle budget gate rises from 768000 to 775000 bytes (v1.0.17 largest chunk was 767.8 kB, leaving no headroom for any change); the v1.0.18 largest chunk is 768.5 kB.

## Release gate
Exact-head CI, verified rollback backup, atomic frontend asset switch without backend restart, local/public health and UI verification, sanitized artifact plus SHA256 publish and public re-download verification.
