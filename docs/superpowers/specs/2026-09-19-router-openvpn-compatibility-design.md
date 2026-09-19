# PVN-029 — Router/OpenVPN Compatibility Design

**Target release:** v1.0.9  
**Status:** design for owner review  
**Primary target:** MikroTik RouterOS and other OpenVPN clients whose UI expects username/password fields.

## Confirmed intent

PVNetwork's normal OpenVPN experience must remain certificate-only: ordinary users keep downloading the same `.ovpn` profiles and are never forced to enter a username or password.

Router compatibility is an explicit opt-in path. It may add authentication requirements only to a separate compatibility listener/profile. The working OpenVPN listener, existing certificates, normal client profiles, active sessions and user provisioning must not be rewritten merely to support routers.

Success means a selected existing PVNetwork user can obtain a router-compatible profile plus credentials for a selected compatible Node, while the same user's normal `.ovpn` profile remains unchanged.

## Compatibility facts driving the design

RouterOS exposes `user` and `password` on its OVPN client and supports importing an `.ovpn` file with `ovpn-user` and `ovpn-password`. Current RouterOS documentation limits usernames to 27 characters and supports client certificates.

RouterOS supports `tls-crypt` only on newer releases and documents a SHA256 constraint for that path. The current PVNetwork normal listener deliberately uses its existing certificate-only configuration and must not be weakened or changed for compatibility.

OpenVPN performs dual authentication when client certificates remain required and `auth-user-pass-verify` is enabled: both the certificate and password verifier must succeed. This is the preferred compatibility mode.

References:
- MikroTik RouterOS OpenVPN documentation: https://help.mikrotik.com/docs/spaces/ROS/pages/2031655/OpenVPN
- OpenVPN alternative authentication: https://openvpn.net/community-docs/using-alternative-authentication-methods.html

## Chosen architecture

Each Node may expose a second OpenVPN instance named `pvnetwork-router`. It is disabled unless the owner explicitly enables Router Compatibility for that Node.

The compatibility instance uses its own config, port, status file, control-plane credential store, static TLS-auth key and tunnel pool. It may reuse the Node's existing CA, server certificate, client certificates and CCD identity so no normal client certificate is rotated.

Default compatibility transport is TCP on a configurable port (initial suggestion: 1195). Before enabling it, the Node checks that the port and tunnel subnet are unused. The UI must allow changing the port rather than assuming `main_port + 1` is safe.

The compatibility profile uses conservative RouterOS-compatible crypto: SHA256 authentication, an explicitly supported AES cipher set, and a separate `tls-auth` key. None of these values are copied back into the normal listener.

## Authentication model

The default router credential is **certificate + password**. The client must present the existing PVNetwork client certificate and a generated router username/password. The verifier also binds that username to the expected certificate Common Name, so credentials cannot be mixed with another user's certificate.

Router usernames are generated as short safe identifiers and stay below RouterOS's 27-character limit. Passwords are high-entropy random values. The plaintext password is shown only at creation/rotation and is never stored in the central database or returned later; if lost, it is rotated.

On each Node, verifier records are stored root-only and contain a salted password verifier, expected certificate Common Name, enabled state and timestamps. Verification uses a memory-hard standard-library derivation and constant-time comparison; credentials are never logged.

Password-only authentication is not the default and is not silently enabled. If a later device truly cannot present a client certificate, that lower-security mode requires a separate explicit design/task rather than weakening this listener during v1.0.9.

## Device-limit and accounting behavior

The compatibility listener keeps certificate `common_name` as the canonical PVNetwork client identity; it does not enable `username-as-common-name`.

It invokes the same PVNetwork connect/disconnect enforcement hooks as the normal listener. Therefore device-limit acquisition/release, central active-session accounting and user enable/disable semantics continue to key off the existing certificate Common Name.

The compatibility instance has a separate status file so Node observability can distinguish its raw sessions. Global online-user truth still deduplicates by the existing PVNetwork user identity and must not count one user twice merely because both listeners are used.

## Panel data model

Add a per-Node compatibility configuration with `enabled`, `port`, `protocol`, and last verified status/version. Existing Node rows default to disabled and retain their normal `ovpn_port` unchanged.

Add router-credential metadata keyed by `(user_uuid, node_id)`: generated short username, enabled state, creation/update/password-change timestamps and last successful authentication timestamp. The panel database does not store the router plaintext password.

Deleting a PVNetwork user, removing its Node assignment, or deactivating it must disable the corresponding router credential. Re-adding a Node assignment does not silently create router credentials; Router Compatibility remains explicitly requested per user/Node.

## Node-side contract

New PVNetwork Node compatibility helpers own only the secondary listener. They may create/update the compatibility config, credential verifier database, Router profile template and systemd instance, but they must never rewrite `server.conf`, the normal client template, the normal tls-crypt key or existing client certificates.

Node API operations are authenticated by the existing panel-to-Node API key and include: compatibility status/preflight, enable/disable configuration, create/rotate/disable a router credential, and download a router-compatible profile for an already-provisioned client Common Name.

Existing Nodes that do not advertise the new capability are shown as `upgrade required`; normal OpenVPN/download operations continue to work. New automatic Node installs include the capability from first boot. Upgrading an existing Node remains an explicit fleet operation with SSH host-key pinning and rollback.

## UI and operator flow

Node Management gets a Router Compatibility status/action. Enabling it shows the proposed port/protocol and a preflight result before any Node mutation. If the Node lacks the capability, the UI directs the operator to the existing pinned-SSH upgrade flow instead of attempting a hidden upgrade.

User Management keeps the normal Download OpenVPN action unchanged. A separate `Router / MikroTik` action appears only for a Node whose compatibility listener is verified healthy and to which the user is assigned.

Creating or rotating credentials returns the short router username and one-time password once, plus a router-compatible `.ovpn` download and a copyable RouterOS import example. The UI states clearly that the normal `.ovpn` needs no username/password and remains the recommended default for ordinary devices.

## Safety and rollback

Enabling compatibility is additive. Before mutation the Node records hashes/copies of every file it may create or replace and snapshots relevant firewall state. It validates port/subnet availability and parses the generated config before starting the secondary instance.

The rollout starts the secondary listener without restarting `openvpn-server@server`. Health checks verify both the new listener and the original normal listener. Any failure stops/removes the new instance and restores its own files/firewall snapshot; the normal listener is not part of rollback because it was never changed.

Production acceptance records normal-listener config/profile hashes and live session count before and after rollout. Those hashes must remain unchanged, existing sessions must remain connected, and normal profile download must still pass.

## Test and release gates

TDD must cover: normal-listener immutability; username length/safe charset; one-time secret behavior; correct/wrong password; correct/wrong certificate CN binding; disabled credential; profile crypto/directives; no plaintext password persistence; user/node deactivation; device-limit hook preservation; Node capability fallback; firewall rollback; and idempotent enable/disable.

A disposable isolated OpenVPN test instance must prove real dual-auth handshakes before Production. Browser tests cover EN/FA desktop/mobile credential generation, rotate/revoke, profile download, error/retry and a Node without the capability.

Production rollout begins on one compatible canary Node only. Required evidence includes app/DB/Node-config backups, main-listener hash/session baseline, secondary-listener health, a non-customer test credential handshake, normal listener/profile regression, 5xx/log checks and rollback readiness. Wider Node enablement follows only after the canary passes.

## Alternatives rejected

1. **Add username/password to the current listener.** Rejected because it changes the authentication contract for every existing client and creates avoidable outage/certificate risk.
2. **Replace the main SHA512/tls-crypt profile with RouterOS-compatible crypto.** Rejected because compatibility should not weaken or churn a working normal profile.
3. **Password-only compatibility by default.** Rejected because OpenVPN explicitly treats certificate+password as the safer dual-auth path and RouterOS supports client certificates.
4. **Store router passwords encrypted for later display.** Rejected for v1.0.9; one-time display plus rotation reduces credential-recovery surface.

## Non-goals for v1.0.9

- No changes to the normal certificate-only user experience.
- No certificate rotation or PKI replacement.
- No automatic enabling on every Node.
- No password-only listener by default.
- No storage of SSH passwords or router plaintext passwords.
- No unrelated Node/upstream naming refactor (tracked separately by PVN-030).

## Release invariants

- **Main-listener immutability:** v1.0.9 may not edit the normal `server.conf`, normal listener port/protocol/crypto, normal client template, existing client certificate/key material, or normal service unit.
- Enabling/disabling Router Compatibility must be reversible without restarting the normal OpenVPN instance.
- Existing normal `.ovpn` output for an unchanged user/Node must remain byte-equivalent apart from pre-existing nondeterministic metadata, if any.
- Compatibility credentials are never created for a user unless the owner/operator explicitly requests them.
