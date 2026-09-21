# PVN-022 / v1.0.16 — Safe Multi-Node Username Rename Design

Status: proposed for owner review
Date: 2026-09-21
Release target: v1.0.16
Scope: PVN-022 only

## 1. Intent

Allow an administrator to rename an existing VPN user's username without deleting/recreating the database user, losing accounting history, widening node assignments, or leaving the old VPN identity usable.

The user UUID is the stable identity. Username remains a mutable login/profile label that must be migrated safely across all assigned Nodes.

Owner decision: **old identity is revoked immediately after successful cutover**. There is no grace period and no manual coexistence mode.

## 2. Success criteria

A successful rename must:

- keep the same `User.uuid`, owner, quota, expiry, usage/accounting records and explicit node assignments;
- create and verify the new per-node OpenVPN identities before touching the old identity;
- preserve the user's active/inactive state on the new identity;
- disconnect and disable the old Common Names at cutover;
- atomically change the central username only after staging succeeds on every assigned Node;
- revoke/delete the old OpenVPN identities after the database cutover;
- never restart the normal OpenVPN service for a per-user rename;
- make old profiles unusable after completion;
- expose deterministic job progress, failure state and retry/rollback behavior.
## 3. Non-goals

This release does not:

- change the user's UUID or subscription UUID;
- add username aliases or grace-period dual identity;
- rename Nodes, administrators or resellers;
- redesign Router/MikroTik credential identity;
- migrate to a new PKI architecture;
- add bulk rename;
- change user-node assignment semantics;
- restart OpenVPN, routing, firewall, Xray or compatibility listeners as part of normal rename.

## 4. Current system constraints

OpenVPN Common Names are currently derived as `<username>-<node.name>`. Existing create/status/delete flows act on those per-node names. User-node assignments are explicit and authoritative.

The user database row has a unique mutable `name` and a stable unique `uuid`. Multiple related tables already key operational state by UUID/node rather than by username; those records must remain attached to the same UUID.

The current edit-user path intentionally leaves username read-only. Rename therefore becomes a dedicated operation rather than silently extending ordinary `PUT /users/{uuid}` behavior.

The v1.0.15 Node lifecycle contract is a prerequisite: per-user activate/deactivate/delete must not restart the whole OpenVPN service.
## 5. Rename workflow

Rename is a durable job with these states:

`queued -> preflight -> staging -> cutover -> revoking_old -> completed`

Failure states are `rolling_back`, `rolled_back`, `cleanup_pending` and `failed`.

### 5.1 Preflight

The server must:

- authorize the actor against the target user;
- normalize/validate the new username using the same username contract as create/Mirza;
- reject no-op rename and existing username collisions;
- lock the target user against concurrent rename/delete/renew/node-assignment mutations;
- snapshot old username, active state, assigned node IDs and relevant username-keyed auxiliary state;
- verify every assigned Node is reachable and supports the v1.0.15 lifecycle capability;
- verify the new per-node Common Name does not already exist unexpectedly.

No externally visible identity changes occur in preflight.

### 5.2 Staging

For every assigned Node, create the new identity `<new_username>-<node.name>` and obtain/verify a fresh profile/certificate. If the central user is inactive, stage the new identity inactive before cutover.

Staging is all-or-nothing. If any Node fails, delete every newly staged identity created by this job and leave the old username and old identities untouched.
### 5.3 Cutover

After all staged identities are verified:

1. Disable and disconnect every old Common Name on assigned Nodes. Do not revoke yet.
2. Confirm no old CN remains active on any reachable assigned Node.
3. In one central database transaction, change `User.name` from old to new and migrate only username-keyed references that semantically follow the user.
4. Commit the transaction.

Before the database commit, rollback is restorative: re-enable the old identities as needed and delete all staged new identities.

The old certificate remains unrevoked only during this narrow rollback window, but the old CN is disabled/disconnected before the transaction is committed.

### 5.4 Revoke old identity

After central commit:

- revoke/delete each old CN using the v1.0.15 per-user lifecycle path;
- regenerate and publish CRL atomically on each assigned Node;
- remove only stale old leaf PKI/profile artifacts;
- verify old CN/profile cannot authenticate;
- keep new identity in the user's original active/inactive state.

A post-commit cleanup failure does **not** roll the database username back automatically. The job enters `cleanup_pending`; the old identity has already been disabled/disconnected and cleanup is retried until revoked/removed.
## 6. Central data migration

`User.uuid` is immutable and remains the primary cross-system identity.

The rename transaction must explicitly inspect and migrate username-keyed references. UUID-keyed tables are not rewritten merely because the display/login name changes.

At minimum the implementation must audit:

- user ownership and reseller accounting references;
- username-based audit/event text where mutable structured fields exist;
- AnyConnect login-facing state while preserving UUID-bound credentials;
- domain/session parsers that derive a user from `<username>-<node>` Common Names;
- generated subscription/profile display metadata;
- any temporary job/lock records introduced by this release.

Historical immutable audit text is not rewritten. New audit events record old username, new username, actor, job ID and timestamps.

Router/MikroTik compatibility credentials remain unchanged when their identity is deterministically UUID/node based. The normal Router profile must continue mapping to the same user UUID.

## 7. API and authorization

Add a dedicated authenticated endpoint under the user UUID, for example `POST /api/users/{uuid}/rename`, accepting the requested new username.

The endpoint returns a job ID immediately. A separate authenticated status endpoint returns only sanitized progress and node IDs/names; it must never expose certificates, private keys, passwords or raw Node secrets.

Delegated admins may rename only users they already own/manage under the existing authorization rules. Main admin keeps global authority. API-token access must follow the existing scope model and may not inherit interactive main-admin privilege implicitly.
## 8. Concurrency and locking

Only one lifecycle mutation may own the user at a time. Rename conflicts with delete, renew/reset operations that write user lifecycle state, status changes, node-assignment changes and another rename.

The implementation must use a durable central lock/job record rather than an in-process-only mutex so worker/process restarts do not allow overlapping mutations.

A stale lock is recoverable only through explicit job recovery logic that inspects the last durable stage and Node state; timeout alone must not silently unlock an unknown half-cutover rename.

## 9. UI behavior

Username stays read-only in ordinary Quick Edit. Add a separate **Rename Username** action/modal.

The modal shows:

- current username and requested username;
- assigned Nodes that will be affected;
- explicit warning that existing OpenVPN profiles for the old username will stop working after successful cutover;
- warning that active sessions using the old CN will be disconnected;
- progress for preflight, staging, cutover and old-identity revocation.

While a rename job is active, destructive/conflicting user controls are disabled for that user. The UI can be closed and later reopened without losing job status.

On success, the Users table/details view refreshes to the new username and offers the new profiles through the existing download/subscription flows.
## 10. Failure handling

Required failure semantics:

- Preflight failure: no changes anywhere.
- Staging failure on any Node: remove all new staged identities created by the job; old identity remains authoritative.
- Failure while disabling old identities before DB commit: re-enable old identities on Nodes already changed and remove staged new identities.
- DB transaction failure: restore old Node state and remove staged new identities.
- Failure after DB commit while revoking old identity: keep new username authoritative and enter `cleanup_pending`; never re-enable the old identity automatically.
- Worker restart: resume from durable job stage and Node evidence, not from assumptions.
- Unreachable Node after commit: old identity on that Node must remain disabled if that state was already achieved; cleanup retries when the Node returns.

Every compensation step is idempotent and safe to retry.

## 11. Test strategy

Blocking TDD/regression coverage must include:

- username normalization, collision and no-op rejection;
- authorization/IDOR checks for main admin, delegated admin and API token scopes;
- same UUID/owner/quota/expiry/usage/assignments before and after rename;
- successful one-node and multi-node rename;
- inactive-user rename remains inactive;
- partial staging failure rolls back all staged new identities;
- cutover failure before DB commit restores old identities;
- cleanup failure after DB commit enters `cleanup_pending` without restoring old access;
- exact-CN handling so `ali` never affects `ali2`;
- old profile authentication fails after completed rename;
- new profile succeeds without normal OpenVPN service restart;
- Router/MikroTik UUID-based credential remains stable;
- AnyConnect login uses new username while UUID-bound credential state remains attached;
- concurrent delete/renew/node-change/rename is rejected or serialized safely.
## 12. Production rollout and release gate

`v1.0.16` follows the existing sequential release contract:

1. exact-head local tests and full CI pass;
2. verified rollback backup of source, database and runtime environment;
3. candidate canary on `19002` with panel/API/UI health checks;
4. deploy canonical panel on `19001` and use the fail-closed Nginx canary-retirement guard;
5. install only the Node capability needed by PVN-022; no normal OpenVPN restart;
6. run a synthetic rename against a dedicated test identity, not a real customer account;
7. prove UUID/assignment/accounting preservation and old-profile revocation;
8. prove normal OpenVPN PID/config hash remain unchanged during rename;
9. run public health/root/users security/smoke checks;
10. publish tag, sanitized artifact, SHA256 and re-download verification.

Any failed Production gate stops the rollout. The canary/rollback state remains available until the failure is understood or the prior state is restored.

## 13. Release evidence

Completion evidence must record:

- exact Git/CI SHAs and runs;
- rollback backup verification;
- synthetic old/new username and Node identities in sanitized form only;
- job state transition evidence;
- unchanged user UUID and explicit assignments;
- OpenVPN PID and server-config hash before/after;
- old-CN disconnect/revoke and new-CN profile verification;
- public HTTP health after canary retirement;
- artifact secret/private-material scan and public SHA verification.

## 14. Acceptance boundary

PVN-022 is complete only when a user can be safely renamed across all assigned Nodes with no silent identity coexistence, no loss of central accounting/assignment state, deterministic rollback before commit, retryable cleanup after commit, and no whole-service OpenVPN restart.

Anything requiring alias/grace-period behavior, bulk rename, PKI redesign or username-independent CN architecture is deferred to a separately numbered future task.
