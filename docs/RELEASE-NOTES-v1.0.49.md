# v1.0.49 candidate — PVN-1033

The controller's download handler prepended the current node endpoint but kept
old `remote` and `proto` lines because two whitespace regexes were double-escaped.
A changed endpoint could therefore produce a file with stale destinations or
conflicting transport settings. Correcting those two literals removes the old
directives before returning the current pair.

The regression calls the actual handler with real SQLite node/user rows and a
controlled node-profile response. It failed on the old source and now passes for
ordinary and whitespace/case variants, preserving inline CA/cert/key content,
other directives, `no-store` and the existing invalid-profile retry/refusal path.
Two focused tests passed. Full Linux regression: 711 tests, 705 passes and six
PostgreSQL-only skips; PostgreSQL code did not change from v1.0.48's six-test pass.

The change modifies only the returned download bytes. It does not rewrite a
cached profile, regenerate identity or restart a node/VPN. No migration is needed.
Native code rollback restores the old download behavior while retaining data.
Final exact-head CI, whole-mission release validation, publication and scoped
Production authorization remain open.
