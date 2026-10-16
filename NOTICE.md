# Notices and attribution

PVNetwork Panel is independently maintained by DashSaman and includes modifications derived from MIT-licensed upstream work.

## Third-party foundations

- Original panel foundation — MIT License — Copyright (c) 2025 PrimeZ.
- `primeZdev/ov-node` — MIT source foundation for the independently versioned `node-agent` package; upstream v1.3.6 commit `fd540b2acfeeac0031e1cf945fc4599fed8e434a`. The full original notice is in `node-agent/LICENSE`.
- `angristan/openvpn-install` — historical legacy bootstrap/profile foundation, pinned by commit in the legacy manifest record. Native fresh nodes use signed distribution OpenVPN/EasyRSA packages and do not fetch or execute this external installer.
- `qrcode-generator` (Kazuhiko Arase) — MIT License — vendored unmodified at `frontend/sub_clients/qr/qrcode.js` and served same-origin for the subscription page QR codes (Copyright (c) 2009 Kazuhiko Arase, http://www.d-project.com/).

The original MIT copyright notice is retained in this repository's `LICENSE` file. PVNetwork modifications, operational tooling, documentation and distribution logic are maintained by DashSaman.

Third-party OpenVPN clients exposed by a deployment are distributed by their respective publishers and remain subject to their own licenses. They are not vendored into this repository.
