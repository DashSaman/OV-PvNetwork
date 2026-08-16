# Installation

## Fresh server

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/DashSaman/OV-PvNetwork/main/install.sh)
```

The interactive installer asks for the admin password when a TTY is available. Non-interactive deployments can set:

```bash
export OVPV_ADMIN_USERNAME=admin
export OVPV_ADMIN_PASSWORD='use-a-strong-password'
export OVPV_PANEL_PORT=19000
export OVPV_PANEL_PATH=panel
export OVPV_SUBSCRIPTION_PATH=sub
bash <(curl -fsSL https://raw.githubusercontent.com/DashSaman/OV-PvNetwork/main/install.sh)
```

## Firewall

Expose only what you actually use. Typical deployments need SSH from trusted management addresses, HTTPS through the reverse proxy, the chosen OpenVPN UDP/TCP port on VPN nodes, and the OV-Node API only from the panel/trusted network.

## Reverse proxy / TLS

The RC installer focuses on the application. Put the public panel behind Nginx/Caddy/another reverse proxy and obtain TLS using your normal certificate workflow. Do not publish the node API to the entire Internet unless you have an explicit reason and firewall policy.

## After installation

```bash
ovpv status
ovpv doctor
```

Use `ovpv backup` before manual source changes.
