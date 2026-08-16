# Feature matrix

This document separates **public RC installer coverage** from **production-derived features that require the sanitized production snapshot before stable 1:1 publication**.

| Area | Status in rc1 | Notes |
|---|---|---|
| Pinned OV-Panel base | ✅ Public | `v1.7.10` |
| Pinned OV-Node base | ✅ Public | `v1.3.6` |
| Pinned OpenVPN installer | ✅ Public | commit in `manifest.json` |
| One-line panel installer | ✅ Public | `install.sh` + `ovpv` manager |
| Update / backup / rollback / doctor | ✅ Public | transactional lifecycle foundation |
| Node profile builder | ✅ Public | rebuilds valid inline `.ovpn` profiles |
| Node NIC counters | ✅ Public helper | provided by `node_patch.py` |
| Avoid routine OpenVPN restart | ✅ Public helper | profile/status operations are designed not to restart the VPN data plane |
| Production health checker | ✅ Public | two failed checks before panel restart |
| Sanitized production exporter | ✅ Public | required before stable parity claim |
| Premium Private Network subscription UI | 🟡 Production-derived | exact current source will enter stable snapshot |
| All-active-user/all-active-node reconciliation | 🟡 Production-derived | current production behavior; stable snapshot required |
| Auto-node deployment UI/backend | 🟡 Production-derived | current production behavior; stable snapshot required |
| Safe node delete/edit lifecycle | 🟡 Production-derived | current production behavior; stable snapshot required |
| Realtime aggregated admin dashboard | 🟡 Production-derived | current production behavior; server-side rate engine is part of latest production work |
| Smart user-page node recommendation | 🟡 Production-derived | page-load sampling; no continuous user polling |
| Monitoring / Telegram alerts | 🟡 Production-derived | exact current source pending snapshot |
| Bandwidth control | 🟡 Production-derived | exact current source pending snapshot |
| Domain activity/history | 🟡 Optional | must never be a hard node-bootstrap dependency |
| Fleet / maintenance / drain / canary operations | 🟡 Production-derived | exact current source pending snapshot |
| AnyConnect / session-control integration | 🧪 Feature-gated | integration hooks exist in production history; deployment remains target-dependent and must be validated before enabling |
| Mirza multi-panel adapter | 🔌 External integration | maintained as a separate integration layer; contains deployment-specific secrets/configuration and is not bundled by default |

## Realtime traffic semantics

For user-facing direction:

- Node **TX** = client **Download**
- Node **RX** = client **Upload**

The production dashboard was moved away from browser-only counter timing because HTTP/cache jitter can create false spikes. Stable publication must preserve per-node timestamp/server-side rate semantics.
