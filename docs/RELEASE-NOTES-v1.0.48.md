# v1.0.48 candidate — PVN-1032

DNS collector batches failed on SQLite with `no such column:
uq_domain_activity_user_node_domain`. The write path used PostgreSQL conflict
syntax and scalar functions. Existing SQLite tables also have a BIGINT primary
key, which SQLite does not populate as an INTEGER rowid alias.

The route now uses the selected database's insert and scalar min/max operations,
with the existing unique user/node/domain key. SQLite IDs are allocated inside
the atomic INSERT under its writer lock, preserving the existing table and data.
PostgreSQL keeps database-generated IDs. Neither backend changes the UUID/node
authorization, site-level domain normalization, time clamping or hit increment.

Validation: the original route failure was reproduced before the fix; five real
SQLite tests passed, including independent concurrent connections in DELETE and
WAL modes, a 1,000-domain batch and full rollback after an injected SQL failure.
The full Linux suite ran 709 tests with 703 passes and six PostgreSQL-only skips.
All six tests then passed against an owned real PostgreSQL service, including
the same domain merge assertion, fresh initialization and existing security gates.

No schema migration or table rebuild is required. Use the verified native update
workflow with a fresh backup. Code rollback does not change schema but restores
the prior SQLite ingestion failure; preserve the database. Production has not
been changed by this candidate. Exact final CI, remaining mission validation,
immutable public assets and scoped deployment approval remain open.

Implementation references: [SQLite writer isolation](https://www.sqlite.org/isolation.html)
and [SQLAlchemy SQLite upsert](https://docs.sqlalchemy.org/en/20/dialects/sqlite.html#sqlite-on-conflict-insert).
