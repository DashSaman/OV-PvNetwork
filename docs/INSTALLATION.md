# Install PVNetwork

[فارسی](INSTALLATION.fa.md) · [README](../README.md) · [Illustrated manual](UI-GUIDE.md)

## 1. Choose the correct path

Fresh installation is for an eligible empty panel target. An existing `/opt/pvnetwork-panel`, panel unit/site, nonempty database or occupied required port is a reason to use the existing installation's verified update/adoption path. Do not reinstall over a working panel.

Supported host checks cover Ubuntu 22.04/24.04 and Debian 12, x86_64/aarch64, at least 1 GiB RAM and 3 GiB free disk. Actual v1.0.54 native installation evidence covers the three distributions; ARM and real public ACME remain separate uncompleted gates. v1.0.55 is a QA candidate; use the command only once its immutable release assets exist and after reviewing its release notes.

## 2. Install in private Setup Mode

1. Log in with authorized root access. Check existing listeners, services and available resources before starting.
2. Run the version-pinned bootstrap on the fresh target:

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/DashSaman/OV-PvNetwork/v1.0.55/install.sh)
```

3. Wait for the final verified result. The bootstrap validates the official archive/SHA256 and metadata; the native installer stages tools, dependencies, database, build, service and managed proxy before activation.
4. Read the initial credentials privately from `/etc/pvnetwork-panel/initial-credentials.txt` as root. This mode-0600 file is not intended for installation logs or public issues.
5. From your own computer, open an encrypted SSH forward, replacing the placeholders with your SSH account and host:

```bash
ssh -L 18443:127.0.0.1:18443 USER@SERVER
```

6. Keep that SSH session open and browse `http://127.0.0.1:18443/panel/` locally. Setup Mode binds to loopback; it is not a public URL and is not a remotely reachable controller for node deployment.

## 3. Fresh target with public HTTPS

1. Prepare a real domain with correct DNS and authorized ACME email. Required public ports 80/443 must be free and ACME validation reachable through your existing network policy.
2. On the eligible fresh target, use:

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/DashSaman/OV-PvNetwork/v1.0.55/install.sh) --domain panel.example.com --email operator@example.com
```

3. Replace the example domain/email first. Until a certificate exists, the owned HTTP site serves ACME challenges and returns 503 for other paths.
4. Wait for certificate issuance, Nginx syntax check and local/public health/UI validation. Use only the final verified URL; failed issuance does not provide a working public HTTPS panel.
5. Check the managed renewal status with the CLI. The installer does not alter firewall rules to make ACME succeed.

For an existing Setup Mode installation, do not run Fresh Install again to add TLS. Inspect `pvnetwork tls --help`, the managed proxy and existing certificate configuration, and perform a separately reviewed TLS transition. Settings path/port changes alone do not issue a public certificate.

## 4. Verify and add a first node

```bash
sudo pvnetwork version --json
sudo pvnetwork status --json
sudo pvnetwork doctor --json
sudo pvnetwork database check --json
sudo pvnetwork jobs --json
```

1. Confirm the installed version, active panel, local health and database checks. Check public HTTPS separately if configured.
2. Sign in, select your language/theme and follow [node installation](NODE-INSTALLATION.md).
3. Create a synthetic test user and follow [profile and VPN verification](UI-GUIDE.md#3-profiles-subscriptions-and-anyconnect).
4. Make a verified native backup and keep a private off-host copy before serving real users.

![Dashboard after sign-in — synthetic Demo](images/v1.0.54/en/desktop/dashboard.png)

## 5. Runtime locations and recovery

| Path | Purpose |
| --- | --- |
| `/opt/pvnetwork-panel` | Active application pointer |
| `/opt/pvnetwork-panel-releases` | Staged/current/previous immutable application releases |
| `/var/lib/pvnetwork-panel/runtime` | Private runtime environment/data for fresh installations |
| `/etc/pvnetwork-panel` | Private credentials, keys and durable operation journals |
| `/opt/pvnetwork-panel-tools` | Privately pinned tools |
| `/var/backups/pvnetwork-panel` | Private verified native backups |

A repeat of the exact completed installation verifies health without regenerating credentials. A different source hash claiming the same version is refused. If Fresh Install was interrupted, inspect its private journal and rerun the same pinned bootstrap with `--recover` only for the matching owned failed transaction. For update/settings recovery, use `sudo pvnetwork recover --yes --json` after inspecting `jobs`. These are different recovery contexts.

Preserve the failed journal and diagnostics. Do not erase a database or directory to force a fresh start. See [native installer details](INSTALLER-CANDIDATE.md), [CLI](CLI.md) and [update/rollback](UPDATES.md).
