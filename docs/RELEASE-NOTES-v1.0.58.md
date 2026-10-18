# v1.0.58 — verified public QA, PVN-1042

Since QA57: improve rendered text/control contrast across themes and scroll positions; name populated node-weight fields; preserve chart series distinction; make node-deployment results a named native dialog with accessible progress/errors, keyboard return and cleared SSH secrets.

Exact-source CI, anonymous artifact verification and official public fresh/repeat installation on Ubuntu 22.04/24.04 and Debian 12, on both x86_64 and real ARM64, pass. The rendered CI gate passes 272 states with 8502 text observations, 840 boundaries and 48 file-control color pairs; 357 axe incomplete groups remain explicit. See [all evidence and limits](VALIDATION-v1.0.58.md) and the [illustrated guide](MANUAL-ACCESSIBILITY-v1.0.58.md).

The frozen release source is `2c6ee6e9b8894125659d87a4bfd99817870a0440`; archive SHA256 is `cff93a239dac5f2b147a1397eb019af6473b68a26dc43d99cb6cc67f0b1d3a60`. Its included documentation records the earlier source-preparation checkpoint. Subsequent publication evidence is recorded here and on the [release page](https://github.com/DashSaman/OV-PvNetwork/releases/tag/v1.0.58); the tag and assets are unchanged.

Evaluate using the version-pinned [installation](INSTALLATION.md) and [update/rollback](UPDATES.md) guides. This release changes the panel UI and current version pins; it adds no database schema migration and does not require replacing an existing node or its credentials. No new Production UI activation or Stable promotion. Supported Stable remains v1.0.37; the live application remains v1.0.55. Actual assistive-technology sessions, public ACME and an independent external fresh-node/client lifecycle remain open. Busy nodes are not empty-server test fixtures.
