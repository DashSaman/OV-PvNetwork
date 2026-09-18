# Node Installation

PVNetwork Panel v1.0.0 uses the panel's automatic SSH deployment workflow as the recommended node installation path.

## Before you start

Use a supported Ubuntu/Debian VPS with root SSH access. The target can host other services, but review existing firewall, NAT, tunnel and routing rules before deployment. Never flush the complete firewall or blindly replace the default route.

## Automatic install

1. Open **Node Management** in the admin panel.
2. Select **Add Node**.
3. Keep **Automatic SSH deployment** enabled.
4. Enter a node name, target SSH address/port, SSH username/password, OpenVPN endpoint/protocol/port and node API settings.
5. Start deployment and keep the progress console open until verification completes.
6. Confirm the node reports healthy metrics and create/download a test user profile.

The deployment workflow installs/pins the compatible node components, applies PVNetwork compatibility/profile patches, creates the management service and verifies the management API before the node is considered ready.

## Safety

On shared nodes, existing unrelated services, NAT/SNAT/MSS rules, tunnels and routes must be preserved. Node API access should be restricted to the panel management source plus loopback. Credentials entered in the deployment dialog must never be committed to the public repository.

## Verification checklist

- Node service is active.
- OpenVPN service is active.
- Node management health endpoint responds.
- CPU/RAM/uptime/network counters appear in the panel.
- A test user can be provisioned on the node.
- The downloaded profile contains CA/certificate/key material and the configured remote/protocol.
- Existing services and routes on the target remain healthy.
