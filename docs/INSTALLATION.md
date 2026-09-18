# Installation

## Fresh panel server

Run as `root` on a fresh supported server:

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/DashSaman/OV-PvNetwork/v1.0.0/install.sh)
```

The installer downloads the tagged release, installs the bundled OV-PvNetwork source, creates runtime secrets locally, builds the frontend, applies database migrations, installs `ov-panel.service`, installs the `ovpv` manager and verifies the local API.

Non-interactive installs can define:

```bash
export PVNETWORK_ADMIN_USERNAME=admin
export PVNETWORK_ADMIN_PASSWORD='choose-a-strong-password'
export PVNETWORK_PORT=19000
export PVNETWORK_PATH=panel
export PVNETWORK_PUBLIC_URL='https://vpn.example.com'
export PVNETWORK_CORS_ORIGINS='https://vpn.example.com'
bash <(curl -fsSL https://raw.githubusercontent.com/DashSaman/OV-PvNetwork/v1.0.0/install.sh)
```

Do not commit these runtime values to Git.
## Add an OpenVPN node

After the panel is healthy, open **Node Management → Add New Node**.

Automatic mode can deploy the supported OV-Node/OpenVPN stack over SSH. Manual mode is available when the node is already prepared. Review shared servers first: node deployment must preserve unrelated routes, firewall rules, tunnels and services.

The node API should only be reachable from the panel or another trusted management network. The OpenVPN listener must be reachable by clients.

## Firewall and TLS

Expose only the ports you actually use. A normal Internet-facing deployment should place the panel behind TLS/reverse proxy and restrict management access. Never publish node-management APIs broadly without an explicit firewall policy.

## After installation

```bash
ovpv status
ovpv doctor
ovpv version
ovpv backup
```

## Existing production servers

The fresh installer intentionally refuses to overwrite a non-empty `/opt/ov-panel`. For an existing deployment, take an application/database backup and use the documented update path instead of re-running fresh installation.

See [UPDATES.md](./UPDATES.md) and the [visual UI guide](./UI-GUIDE.md).
