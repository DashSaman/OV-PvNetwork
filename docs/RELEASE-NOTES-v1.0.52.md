# v1.0.52 candidate — PVN-1036

The exact private v1.0.51 QA archive failed a real fresh Ubuntu 24.04 install at Bash `set -Eeuo pipefail`. Git blobs were LF, but `git archive` inherited this Windows contributor's `core.autocrlf=true` and exported all nine shell files as CRLF. This is an artifact creation failure, not proof that earlier Linux-built public archives have the same bytes.

Repository attributes now require LF for auto-detected text and explicitly preserve binary images, fonts and archives. The runtime, dependencies, installer logic and UI are unchanged. Existing version-labelled v1.0.51 Demo captures remain current.

Four regressions use a real temporary Git repository and the project's attributes. Windows-style archive settings now preserve exact shell bytes and executable bits, binary hashes and identical archive bytes between autocrlf settings. The actual exported entry point executes in Linux Bash. The old policy failed before correction. All four tests and twelve related Linux version/settings contracts passed; Windows passed its three applicable tests and explicitly skipped Linux Bash execution.

A new clean exact source archive must pass fresh/repeat installation and native lifecycle acceptance before publication. The failed private archive is retained as evidence and will not be published. No released tag or historical asset is rewritten. No migration or Production mutation is included. Final exact CI, artifact and separately scoped Production gates remain open.
