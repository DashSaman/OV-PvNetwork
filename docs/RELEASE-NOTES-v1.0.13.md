# PVNetwork Panel v1.0.13 — PVN-894

PVN-894 hardens the Production release procedure after the v1.0.12 rollout exposed a canary-retirement ordering bug.

## Canary retirement guard
- Refuses retirement if the active Nginx site still proxies to `127.0.0.1:19002`.
- Refuses retirement if canonical `127.0.0.1:19001` is not the configured panel upstream.
- Requires `nginx -t` to pass.
- Reloads Nginx only after the site file is proven to reference canonical rather than canary, then performs health checks against the reloaded proxy.
- Requires local canonical `/healthz` HTTP 200.
- Requires the operator-supplied public `/healthz` URL to return HTTP 200.
- Emits `CANARY_RETIRE_SAFE=YES` only after every gate passes; otherwise returns non-zero with `CANARY_RETIRE_SAFE=NO`.

## Safety boundary
- This release does not modify normal OpenVPN, Router compatibility listeners, `ov-node.service`, certificates, profiles, routing, firewall policy or active VPN tunnels.
- The guard is release-control-plane tooling; it may reload Nginx after configuration validation but does not stop the canary or restart panel/OpenVPN/Node by itself. Operators stop a canary only after the guard passes.
