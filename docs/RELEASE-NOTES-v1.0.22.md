# PVNetwork Panel v1.0.22 — Reliable automatic node deployment

`PVN-1008` repairs the Add-Node automatic installer's most damaging failure modes.

## Problem 1 — "Panel IP"
The Add Node form prefilled "Panel public IP" with `window.location.hostname`. When the panel is used through a domain (behind Cloudflare/nginx), that value is a hostname, not an IP:

- The backend's strict `ip_address()` validation rejected it immediately with a cryptic raw error (`X does not appear to be an IPv4 or IPv6 address`) — deployment never started.
- Filling an IP manually was error-prone: any mistake (NAT, proxy, stale address) installed the node fully, then the node-side firewall allowlisted the wrong source and panel verification failed at the very end after ten-plus minutes.

## Fix — auto-detected panel source
- `panel_ip` is now optional end-to-end (schema, API and UI).
- When it is empty or not a literal IP, the install script derives the allowlist source **on the node from the SSH session itself** (`$SSH_CLIENT`/`$SSH_CONNECTION`): the panel connects to the node over SSH to install it, so this is guaranteed to be the address its API calls will come from.
- The decision (explicit vs auto-detected) is logged in the deployment terminal; an unresolvable source aborts with a clear `PANEL_SOURCE_IP_UNRESOLVED` marker instead of writing a broken firewall.
- The optional field remains for the rare case where panel API traffic genuinely leaves from a different address than SSH.

## Problem 2 — firewall rule insertion
Allow rules were inserted at `INPUT` position 2; on servers whose INPUT chain has zero or one rule this errors and rolls back an otherwise successful install.

## Fix — robust rule shape
- Existence-guarded inserts at position 1, DROP appended at the end (order remains allow-before-drop).
- IPv6 panel sources get a matching `ip6tables` allow branch; the previous blanket IPv6 DROP (which could lock out IPv6-reachable panels) is gone.

## Also
- Post-install verification failures now report "panel could not reach the node API" with concrete checks instead of a bare timeout string.
- Add-Node SSH field labels are translated in all 13 languages.
- Focused contract tests cover the auto-detect classifier, hostname tolerance, embedded literals, rule shape, IPv6 branch, optional schema and modal wiring.

## Scope and safety
Only the Add-Node automatic deployment path changes. Manual node registration, existing nodes, OpenVPN, Router compatibility listeners, profiles and sessions are untouched. `pvnetwork-panel.service` restart is the only deployment restart.

## Release gate
Exact-head CI, atomic frontend switch plus backend delta, local/public health verification, sanitized artifact plus SHA256 publish and public re-download verification.
