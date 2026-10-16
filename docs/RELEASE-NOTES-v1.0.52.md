# v1.0.52 candidate — PVN-1036

The exact private v1.0.51 QA archive failed a real fresh Ubuntu 24.04 install at Bash `set -Eeuo pipefail`. Git blobs were LF, but `git archive` inherited this Windows contributor's `core.autocrlf=true` and exported all nine shell files as CRLF. This is an artifact creation failure, not proof that earlier Linux-built public archives have the same bytes.

Repository attributes now require LF for auto-detected text and explicitly preserve binary images, fonts and archives. The runtime, dependencies, installer logic and UI are unchanged. Existing version-labelled v1.0.51 Demo captures remain current.

Four regressions use a real temporary Git repository and the project's attributes. Windows-style archive settings now preserve exact shell bytes and executable bits, binary hashes and identical archive bytes between autocrlf settings. The actual exported entry point executes in Linux Bash. The old policy failed before correction. All four tests and twelve related Linux version/settings contracts passed; Windows passed its three applicable tests and explicitly skipped Linux Bash execution.

A new clean exact source archive must pass fresh/repeat installation and native lifecycle acceptance before publication. The failed private archive is retained as evidence and will not be published. No released tag or historical asset is rewritten. No migration or Production mutation is included. Final exact CI, artifact and separately scoped Production gates remain open.

The first corrected exact archive (commit `91fa091e96d22b3f8ae6d6936579535ccc7935f0`, SHA256 `2a06712ac1ea1ccefba1f1ce7fc6375f3428bf1151f9ff23b312c033a2b1cd9f`) passed actual isolated native 1.0.45 → 1.0.52 → 1.0.45 update/rollback, preserving existing rows/environment/health. Fresh Ubuntu progressed past Bash but the local host exhausted storage and its guest filesystem became read-only; it is NOT a fresh-install PASS. No global host repair/restart was performed.

A separate CI matrix now builds pinned Ubuntu 22.04/24.04 and Debian 12 disposable systemd guests. Each consumes the exact checked-out Git archive with Windows-style export settings and validates fresh/repeat install, real panel/proxy/UI assets, SQLite head/integrity, secret-file permissions and installed CLI. It publishes no ports or raw runtime/credential logs and cleans only its own guests/images. These checks remain pending until the exact CI jobs pass. Public ACME/external VPS coverage remains explicitly conditional.
