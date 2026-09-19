# Installation

## Fresh panel server

Run as `root` on a **fresh** supported server:

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/DashSaman/OV-PvNetwork/v1.0.2/install.sh)
```

The installer downloads the tagged release, installs the bundled PVNetwork source, creates runtime secrets locally, builds the frontend, applies database migrations, installs `ov-panel.service`, installs the lifecycle manager where supported and verifies the local API.

Non-interactive installs can define:

```bash
export PVNETWORK_ADMIN_USERNAME=admin
export PVNETWORK_ADMIN_PASSWORD='choose-a-strong-password'
export PVNETWORK_PORT=19000
export PVNETWORK_PATH=panel
export PVNETWORK_PUBLIC_URL='https://vpn.example.com'
export PVNETWORK_CORS_ORIGINS='https://vpn.example.com'
bash <(curl -fsSL https://raw.githubusercontent.com/DashSaman/OV-PvNetwork/v1.0.2/install.sh)
```

Do not commit runtime values to Git.

## Critical rule for existing/production servers

Assume an existing server is **live and under load**. The fresh installer intentionally refuses to overwrite a non-empty `/opt/ov-panel`.

For an existing deployment:

1. verify service/API health;
2. create application/database backup appropriate to the deployment;
3. review the target release and migrations;
4. use the update/migration path instead of Fresh Install;
5. restart only the required service;
6. verify local/public health and critical workflows;
7. roll back when verification fails.

Do not flush firewalls, replace default routes, remove unrelated tunnels/services, recreate working nodes, or rotate healthy credentials/certificates merely to simplify an upgrade.

## Add an OpenVPN node

After the panel is healthy, open **Node Management → Add New Node**.

Automatic mode can deploy the supported OV-Node/OpenVPN stack over SSH. Manual mode is available when the node is already prepared. Review shared servers first: node deployment must preserve unrelated routes, firewall rules, tunnels, databases and services.

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

## Responsive admin UI

v1.1 adds mobile/tablet hardening and complete Main Admin navigation on narrow screens. After installation, verify the core UI at phone/tablet/desktop widths and both Persian RTL/English LTR if those languages are used.

See:

- [Updates and rollback](./UPDATES.md)
- [English visual UI guide](./UI-GUIDE.md)
- [Persian visual UI guide](./UI-GUIDE.fa.md)
- [Responsive guide](./RESPONSIVE-GUIDE.md)
- [راهنمای Responsive فارسی](./RESPONSIVE-GUIDE.fa.md)
