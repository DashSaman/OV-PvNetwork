# Updates and rollback

## Production safety first

PVNetwork Production is assumed live and under load. Do not update by replacing the live tree blindly.

Before changing Production:

```bash
pvnetwork doctor
pvnetwork backup
```

If you use PostgreSQL, keep a database-native backup as well; an application backup does not replace the database backup policy.

Record the current version/service health and have a rollback target before restarting anything.

## Update to latest stable release

```bash
pvnetwork update
```

Where the lifecycle manager is installed, it resolves the latest published GitHub Release, creates a pre-update backup, downloads the tagged source, preserves runtime `.env`/state, applies required migrations/builds, restarts only `pvnetwork-panel.service`, then verifies the local API. Failed health verification must trigger rollback rather than repeated blind mutation.

## Target a specific patch explicitly

```bash
PVNETWORK_REF=v1.0.2 pvnetwork update
```

A branch name can be used in a disposable/staging environment, but Production should normally consume a reviewed tagged release.

## Sequential patch update notes

Patch releases are sequential. Review the target release notes before every update; a patch may include UI, backend or additive database migrations, but must preserve the live-Production safety contract and document upgrade/rollback requirements.

After upgrading, verify:

- login and Dashboard;
- Users, Renew and Reset Usage;
- Nodes and node-health view;
- Main Admin mobile **More** navigation;
- Operations, Security, Fleet, Monitoring and Bandwidth pages;
- Persian RTL and/or English LTR as used by your deployment;
- local and public panel health.

## Rollback

Rollback to the most recent application backup:

```bash
pvnetwork rollback
```

Or choose a backup directory:

```bash
pvnetwork rollback /var/backups/pvnetwork-panel/YYYYMMDD-HHMMSS
```

Rollback must restore the captured application/runtime state, rebuild required assets/dependencies, restart only the panel service and verify health.

## Never do this as a normal update shortcut

- Do not flush iptables/nftables wholesale.
- Do not replace the host default route.
- Do not remove unrelated tunnels, x-ui/Xray, databases or other host services.
- Do not delete/recreate working nodes merely to make an update easier.
- Do not rotate healthy user/node certificates or credentials without a task-specific reason.

## Status and version

```bash
pvnetwork status
pvnetwork version
pvnetwork doctor
```

## Release rule

Every Production-visible change updates `VERSION`, `CHANGELOG.md`, release notes and a new tagged GitHub Release. Released tags/assets remain immutable. See [QA-RELEASE-GATE.md](./QA-RELEASE-GATE.md) for blocking release checks.
