# Add and verify a PVNetwork node

[فارسی](NODE-INSTALLATION.fa.md) · [Web manual](UI-GUIDE.md#4-nodes)

![Node deployment form](images/v1.0.54/en/desktop/node-create.png)

## 1. Prepare the target and SSH trust

1. Verify supported Ubuntu/Debian, resources, authorized root SSH access and actual host state. A host already running VPN/tunnels is not a fresh node.
2. Inspect existing ports, VPN configuration, services, subnet routes and firewall. Back up existing node state privately before any explicit adoption.
3. Obtain the SSH host SHA256 fingerprint through an independently trusted console/channel. The dialog can use that fingerprint or a previously trusted host key; do not accept a changed fingerprint just to proceed.
4. Ensure the node can reach the issuing controller's real HTTPS origin and the panel can reach the node's chosen HTTPS API port. The controller is an origin, such as `https://panel.example.com`, without the panel path. `.example` is a placeholder.

## 2. Automatic SSH deployment

1. In **Node Management → Add New Node**, keep Automatic SSH mode and enter name, target address, SSH port/user and password or private key. Secrets remain private; do not paste them into Git/issues.
2. Choose **Fresh server** only for an eligible empty target. Choose **Adopt existing node** only for a supported existing registered node, supplying its existing ID and preserving its name, address, VPN port and protocol. Adoption requires a free new HTTPS API port and compatible protected management/PKI state; unsupported hooks or operator state may be refused.
3. Review API port, VPN port/protocol, tunnel address, controller HTTPS origin and SSH fingerprint. API and VPN listeners have distinct purposes and must not collide. Leave optional panel-source IP empty unless the detected SSH source differs from the required management source (for example NAT); then supply the correct source deliberately.
4. Submit once. Follow the job through source checksum/proof, preflight, installation, authenticated HTTPS health, registration and remote finalization. A progress connection closing does not mean the persistent job finished.
5. Refresh inventory only after the terminal result. On failure inspect the job/recovery before submitting again; do not erase live node configuration.

The panel builds the compatible node bundle from reviewed repository source. It verifies SSH trust, source integrity and a short-lived controller proof. Native deployment rejects incompatible live state rather than blindly replacing it. Read [native node constraints/evidence](NODE-CANDIDATE.md), especially fresh/adopt differences.

## 3. Manual registration

1. Choose Manual mode only for an already prepared compatible node.
2. Enter the correct node identity, management address/port/key, VPN endpoint/protocol and other required fields.
3. Verify the management API from the panel and inspect the recorded transport/binding. Manual registration does not automatically install VPN, create a CA or turn an arbitrary HTTP service into a trusted native HTTPS node.
4. Use the test below before assigning customers.

## 4. Validate the complete path

![Node inventory](images/v1.0.54/en/desktop/nodes.png)

1. Confirm the registered node's authenticated health, version and metrics. A green HTTP response alone is insufficient.
2. Create a synthetic user assigned to that node and download its profile. Confirm the intended remote/protocol and complete private certificate/key material without publishing the file.
3. Import into a compatible client, complete TLS/TUN negotiation and move actual traffic through the tunnel. Test UDP/TCP only when each protocol is deliberately configured.
4. Check integer usage counters and presence in the panel. Disconnect/reconnect and verify consumption remains consistent; test concurrent-device policy if used.
5. Disable the test account and verify its access is removed while an unrelated test account remains usable. Confirm unrelated services/routes/firewall policy and, for adoption, the running VPN identity/PID are preserved.

## 5. Maintenance and recovery

Drain before intended maintenance, inspect scoped reconcile/repair jobs and wait for verified results. Agent code upgrade is separate from VPN recreation. Use [node archives](NODE-ARCHIVES-CANDIDATE.md) for owned backups/restore/recovery. Do not delete/recreate a working node to bypass a failed job or last-node guard.

[Phone form](images/v1.0.54/en/mobile/node-create.png) · [Phone inventory](images/v1.0.54/en/mobile/nodes.png) · [Fleet guide](UI-GUIDE.md#8-advanced-node-management)
