# PVNetwork Panel v1.0.12 — PVN-032

PVN-032 adds guarded runtime controls for the panel URL path and the main-administrator username/password from the authenticated Security Settings page.

## Main-admin security
- Every mutation requires the current main-admin password again.
- A new password is persisted only as the existing one-way password hash; plaintext passwords are not written to job state, logs or release artifacts.
- Main-admin JWTs carry `MAIN_ADMIN_AUTH_GENERATION`. A successful username/password rotation changes that generation so older main-admin browser JWTs stop validating.
- The initiating browser uses a short-lived pending replacement token and promotes it only after the change job reaches `complete`.
- Existing TOTP state follows a successful main-admin username rename and is restored if the switch rolls back.

## Panel-path switch
- A candidate frontend is built with the requested path and a candidate panel is verified on `127.0.0.1:19002` before Production mutation.
- The live `.env` and frontend distribution are switched atomically after preflight succeeds.
- Canonical verification has a finite timeout; a failed post-switch verification restores the exact previous panel environment/frontend and restarts only the panel service.
- The previous panel path returns HTTP **307** to the same suffix on the new path for exactly **300 seconds**, then the old path naturally returns 404.

## VPN and Node isolation
- PVN-032 may restart only `pvnetwork-panel.service`.
- Normal OpenVPN listeners, the optional Router/MikroTik compatibility listener, `ov-node.service`, certificates, profiles, routing, firewall policy and active VPN tunnels are not reconfigured or restarted by this feature.
- Production acceptance requires before/after PID and normal OpenVPN configuration-hash evidence proving that isolation.
- Rollout guard fix: the Node healthcheck now uses the Node API's real `GET /sync/status` request shape, avoiding false 405-triggered `ov-node.service` restarts; the smoke checker no longer shell-sources `.env`, so bcrypt hashes cannot be expanded as shell variables, and it validates nested FastAPI routes through the in-process schema.

## Recovery and release verification
- Runtime change state is secret-free and guarded by a non-blocking single-change lock.
- The detached helper keeps a rollback snapshot before canonical mutation and reports `complete` or `rolled_back` through a short-lived change-status token.
- CI covers backend contracts, browser handoff/resume behavior, mobile responsiveness, secret scanning and the existing JavaScript bundle budget.
- The public v1.0.12 artifact must be sanitized, accompanied by SHA256, downloaded again after publishing, and re-verified before the release is closed.
