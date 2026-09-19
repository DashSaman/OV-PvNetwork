# PVNetwork Panel v1.0.9 — Router / MikroTik OpenVPN Compatibility

PVN-029 adds an **opt-in secondary OpenVPN path** for RouterOS and other clients that expect username/password authentication. The existing normal OpenVPN listener and normal `.ovpn` profiles remain certificate-only and unchanged.

## What is new

- Per-Node secondary listener with independent port, protocol, tunnel subnet, status file, firewall rules and rollback snapshot.
- Certificate + password dual authentication. The certificate Common Name remains the canonical PVNetwork user identity.
- Per-user/per-Node Router username and password. Plaintext passwords are returned only on Generate/Rotate and are never persisted centrally.
- Dedicated Router `.ovpn` profile and a copyable RouterOS import command.
- Old Nodes report `upgrade_required`; normal Node/OpenVPN actions continue to work.
- Secondary listener sessions are merged into display presence by Common Name without double-counting and without writing synthetic `active_sessions` rows.
- EN/FA desktop/mobile UI coverage and real isolated OpenVPN handshake regression tests.

## Safety invariants

- `/etc/openvpn/server/server.conf`, the normal OpenVPN service PID/config, normal profile template and existing client profiles are not rewritten by Router compatibility enable/disable.
- Normal users do not receive or need Router credentials.
- Enabling/disabling Router compatibility does not restart `openvpn-server@server`.
- Port/subnet collision fails before mutation; failed secondary enable rolls back only secondary files/firewall state.
- User disable/delete or assignment removal revokes the corresponding Router credential on a best-effort basis after the authoritative user/assignment decision.

![Router user flow](./images/v1.0.9/en/desktop/router-user.png)

![Router node flow](./images/v1.0.9/en/mobile/router-node.png)
