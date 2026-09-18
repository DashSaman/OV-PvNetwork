# PVNetwork Panel v1.0.0 Release Baseline Design

## Goal
Freeze the current production platform as the first stable PVNetwork Panel release after adding safe expired-user renewal, and ship reproducible installation, upgrade, backup, rollback, bilingual documentation, screenshots, release notes, and a prioritized competitive roadmap.

## Scope
1. Expired-user renewal without delete/recreate.
2. Preserve UUID, username, node assignments, subscription URL, and AnyConnect identity.
3. Support unlimited and finite plans with optional traffic reset/add.
4. Record renewal in audit history and expose it to Mirza integration.
5. Keep node synchronization and profile verification fail-safe.
6. Produce English and Persian README/user/admin/install/update documentation.
7. Add sanitized visual guides for every major page/action.
8. Add main-panel and node installers plus doctor/update/backup/rollback helpers.
9. Package the stable baseline as v1.0.0 and define SemVer release policy.
10. Publish a competitive feature matrix and prioritized roadmap.

## Safety Constraints
- Production data must never be deleted as part of renewal or release preparation.
- Back up before every production mutation.
- Never expose passwords, API keys, private certificates, customer identifiers, or production database content in the public repository.
- Do not replace existing firewall/routing rules wholesale.
- Preserve backward-compatible internal paths and systemd unit names in v1.0.0 where renaming could break production.
- Release only after build, compile, migration, health, installer dry-run, and renewal regression verification succeed.

## Release Model
- v1.0.0: first stable production baseline.
- v1.0.x: backwards-compatible fixes.
- v1.x.0: backwards-compatible features.
- v2.0.0: breaking protocol/schema/operational changes.

## Documentation Model
README.md is English-first; README.fa.md is Persian-first. Each major workflow receives a matching bilingual document and sanitized screenshots. Every release updates CHANGELOG.md and release notes.

## Competitive Roadmap
Benchmark against actively maintained OpenVPN, Xray, multi-node, reseller, observability, and enterprise-access panels. Missing features are tracked as numbered roadmap items and GitHub issues, separated into core priorities and optional universal-protocol expansion.