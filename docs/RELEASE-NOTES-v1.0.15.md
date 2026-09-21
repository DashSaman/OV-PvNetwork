# PVNetwork Panel v1.0.15 — Per-user OpenVPN lifecycle preservation

`PVN-376` / `PVN-398` remove whole-service OpenVPN restarts from routine per-user lifecycle operations.

## Behavior
- **Enable:** creates/repairs only the target client's CCD state; no OpenVPN restart.
- **Disable:** removes the target CCD and disconnects only that Common Name through the management socket.
- **Delete:** removes target access, disconnects that CN, revokes its certificate with EasyRSA, regenerates/publishes the CRL atomically, then removes only the target client's stale PKI leaf artifacts and profile.
- Existing Node capability upgrades now install this lifecycle patch instead of updating Router compatibility alone.

## Safety
The patch does not alter the normal OpenVPN listener/server configuration, routing or firewall. Node patching is idempotent and supports the Production management socket with the legacy socket as fallback. No database migration is required.

## Verification gate
Focused lifecycle tests must prove exact-CN behavior and absence of `systemctl restart`. Full CI must pass before Production. Production rollout requires a verified rollback copy, compile/API health, and evidence that the normal OpenVPN PID and configuration hash remain unchanged while synthetic per-user lifecycle probes execute.
