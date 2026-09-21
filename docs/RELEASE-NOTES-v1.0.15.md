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
## Production verification
- Exact-head PR CI, legacy-Node hotfix CI and merged-main CI passed before the final Production patch.
- A verified rollback point covered source, database and runtime environment.
- A unique synthetic CN completed Activate -> Disable -> Delete on the deployed Node.
- The normal OpenVPN PID and server-config hash remained unchanged throughout the lifecycle probe.
- CRL regeneration completed and the published CRL remained OpenSSL-valid.
- Canonical panel health reported `1.0.15`, and public health/panel/users remained HTTP 200 after canary retirement.

The Production probe also caught and fixed a legacy-Node compatibility gap before release: the injected lifecycle block is now self-contained and does not depend on a pre-existing `_safe_name` helper.
