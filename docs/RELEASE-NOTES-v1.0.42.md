# 1.0.42 — PVN-1026 candidate

Native verified backup/restore, staged schema-compatible updates, atomic release switching, scoped writer pauses and durable interruption recovery replace direct runtime replacement. Previous code, live data and runtime secrets are retained. PostgreSQL dumps are actually restored; SQLite committed WAL rows and owned crypto/trust files are verified. [Scope, commands, evidence and remaining gates](LIFECYCLE-CANDIDATE.md). This candidate is not yet public stable or deployed to Production.
