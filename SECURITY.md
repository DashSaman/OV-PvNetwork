# Security policy

## Reporting

Please avoid publishing live credentials, private keys, VPN profiles, API keys or exploitable deployment details in a public issue. Contact the maintainer through the repository owner account for sensitive reports.

## Deployment rules

- Use unique strong panel/admin credentials.
- Keep `.env` mode `0600` and never commit it.
- Restrict OV-Node API access to the panel/trusted network.
- Use TLS for public panel/subscription traffic.
- Firewall every node and expose only required VPN/management ports.
- Rotate node/API/JWT credentials after any suspected disclosure.
- Treat SSH credentials used for auto-node deployment as highly privileged.
- Never commit databases, customer identifiers, `.ovpn` profiles, certificate private keys, notification tokens or chat credentials.

## Update safety

Back up before upgrades and validate local API health before considering an update successful. OV-PvNetwork intentionally avoids routine OpenVPN restarts during control-plane maintenance.
