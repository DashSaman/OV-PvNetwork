# PVNetwork Panel v1.0.16 — Safe Multi-Node Username Rename

`PVN-022` adds a dedicated durable username-rename workflow without deleting and recreating the central user.

## Identity preservation
The user UUID remains immutable. Owner, quota, expiry, used traffic/accounting, concurrent-device limit, explicit node assignments, UUID-bound AnyConnect credential state and UUID/node-based Router/MikroTik credentials are preserved. Historical audit text is not rewritten.

## Safe OpenVPN cutover
The new `<username>-<node>` identities are staged and verified on every assigned Node first. Cutover then disables and disconnects the old CNs, atomically commits the central username, and immediately revokes/deletes the old identities. There is no grace period: old OpenVPN profiles are invalid after successful completion.

Rename uses only per-user lifecycle operations and never calls a whole-service OpenVPN restart.

## Failure semantics
Before the DB commit, any staging/cutover failure triggers restorative `rollback`: old identities are restored when originally active and staged new identities are removed. After commit, the new username remains authoritative. If old identity revocation is incomplete, the durable job enters `cleanup_pending`; old access is never intentionally re-enabled, and cleanup is retryable/idempotent.

A durable lifecycle lock blocks conflicting edit/reset/renew/node-assignment/status/delete operations while rename owns the user. Worker restarts resume from persisted state rather than assumptions.

## UI and API
Username stays read-only in Quick Edit. A separate Rename Username dialog explains immediate old-profile invalidation and session disconnect, shows assigned Nodes and durable progress, recovers active jobs after browser refresh, and supports cleanup retry.

## Release gate
Production completion requires exact-head CI, verified rollback backup, Alembic migration, canary on `19002`, canonical cutback through the fail-closed Nginx guard, a synthetic rename only, proof that UUID/accounting/assignments remain unchanged, old-profile revocation/new-profile validity, unchanged normal OpenVPN PID/config hash, public health checks, sanitized artifact, SHA256 and public re-download verification.
