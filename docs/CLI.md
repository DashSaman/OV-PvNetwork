# PVNetwork operational console — v1.0.56 QA

Run `sudo pvnetwork` for the 25-item console. Select English or Persian with `--lang en` / `--lang fa`; menu 24 saves the preference privately. `pvnetwork --help` and each subcommand's `--help` describe automation arguments. Noninteractive execution requires a command.

| Menu | Command | Scope |
| --- | --- | --- |
| 1 | `status` | Installed version, panel service, local health and dashboard |
| 2 | `services` | One named panel service or owned timer; status/start/stop/restart/enable/disable |
| 3 | `nodes` | List/health/deploy/edit/drain/undrain/enable/disable/reconcile/remove/backup/restore/recover/job |
| 4 | `sessions` | Presence, or one `--user-id` |
| 5 | `logs` | One allowlisted unit, at most 500 lines, redacted |
| 6 | `troubleshoot` | Read-only health checks |
| 7 | `doctor` | Read-only checks; exit 69 if unhealthy |
| 8 | `repair` | One panel service, timer or registered node |
| 9–12 | `update`, `backup`, `restore`, `rollback` | Existing verified native lifecycle engines |
| 13 | `tls inspect` / `tls renew` | Certificate inspection; renewal of the selected managed ACME cert-name |
| 14–15 | `settings`, `credentials` | Current state or staged apply after checking the current admin password |
| 16–18 | `firewall`, `network`, `nginx` | Read-only rules summary, interfaces/routes and managed proxy inspection/syntax |
| 19 | `database` | Read-only backend/integrity/migration inspection; schema upgrades remain part of verified update |
| 20–22 | `resources`, `jobs`, `version` | Resource facts, owned timers/recovery journals and version |
| 23 | `support` | Private structured support archive, without raw logs/config/customer data |
| 24–25 | `language`, Exit | Saved EN/FA preference and exit |

Every mutation accepts `--dry-run`; this prints its selected operation without accessing services, accepting secrets or changing files. Except backup, support export and language preference, mutations require explicit `YES` or `--yes`. Root is required. VPN/node service units and arbitrary shell commands are outside the services allowlist.

```sh
sudo pvnetwork --lang en
sudo pvnetwork doctor --json
sudo pvnetwork services restart --unit pvnetwork-panel.service --dry-run --json
sudo pvnetwork repair --scope node-reconcile --node-id 7 --yes --json
sudo pvnetwork nodes job --node-id 7 --job-type reconcile --job-id <returned-job-id> --json
sudo pvnetwork nodes job --job-type deploy --job-id <returned-job-id> --json
sudo pvnetwork logs --lines 100 --json
sudo pvnetwork database check --json
sudo pvnetwork support --output /root/pvnetwork-support.tar.gz --json
sudo pvnetwork update v1.0.56 --yes --json
sudo pvnetwork restore 20261016-120000 --yes --json
sudo pvnetwork recover --yes --json
```

The update example works only after an immutable release and its exact SHA256 asset are published. A candidate branch is not an update source. Existing flat JSON output for lifecycle/version/status commands is preserved.

Interactive credentials use hidden password prompts or a private key file. Automation uses `--input-json-stdin` with a bounded JSON object from a private source. Do not put secrets in command arguments, shell history, public logs or example files. The local client signs a short-lived root-admin token in memory and sends it only to the fixed loopback API, with proxies and redirects disabled. It redacts tokens from results.

`settings apply` accepts `current_password` and optional `new_path` / `new_port`; `credentials apply` accepts optional `new_username` / `new_password`. Port changes select a free internal port 1024–65535 except canary port 19002; public HTTPS listeners and firewall are preserved. A private candidate build and canary precede the live switch. Previous env, build and managed proxy are retained; `recover` handles interrupted switches and refuses unknown operator edits. A failed rollback stays `recovery_required` until verified.

Node reconciliation checks profiles for that registered node only, preserves assignments and drain flags, and never restarts VPN. Explicit existing user assignments remain authoritative. Node edit preserves an omitted stored credential. Renaming a node with live identity references is refused because the current profile CN includes its name. Removal uses the existing assignment/last-node guards. Node backup/restore retains the SSH trust, node binding and offline-recovery requirements described in [node archives](NODE-ARCHIVES-CANDIDATE.md).

TLS renewal selects the one ACME certificate used by the managed panel site. It does not force renewal, select every certificate or restart VPN. It checks Nginx syntax before graceful reload. Database diagnostics use read-only transactions and deadlines. Support archives are mode 0600, require a private absolute parent directory and never overwrite an existing file.

Exit codes: 0 success; 64 invalid usage; 69 unhealthy/unavailable; 70 operation failure; 75 busy/pending recovery; 77 root/confirmation required; 130 interrupted. A queued node/settings response indicates acceptance; inspect its terminal status before treating an operation as successful.

Current QA release evidence and remaining gates are recorded in [v1.0.56 validation](VALIDATION-v1.0.56.md). The owner-authorized live deployment remains v1.0.55. The native snapshot log policy introduced in v1.0.55 is described in [its notes](RELEASE-NOTES-v1.0.55.md). [Illustrated web manual](UI-GUIDE.md) · [فارسی](CLI.fa.md).

## First operational session

1. Run `sudo pvnetwork --lang en`, choose **1 Status**, then **7 Doctor**. Read each failed check before any repair.
2. Inspect **22 Version**, **19 Database**, **21 Jobs** and **5 Logs** as needed. These diagnostic paths do not authorize a blanket restart.
3. For a change, read that command's `--help`, select one target and run its `--dry-run`. Review the selected scope before explicit confirmation.
4. Use **10 Backup** and retain its verified path before update/restore/settings work. Directory existence alone does not prove verification.
5. For queued work, save the job ID and inspect it until a terminal verified result. On interruption inspect **21 Jobs** and the supported recovery command before launching another change.
6. After mutation, run Status/Doctor again and test the changed workflow. Keep support exports private. Choose **24 Language** to save preference and **25 Exit** to leave.
