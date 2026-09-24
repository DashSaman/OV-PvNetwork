# Notices and attribution

PVNetwork Panel is independently maintained by DashSaman and includes modifications derived from MIT-licensed upstream work.

## Third-party foundations

- Original panel foundation — MIT License — Copyright (c) 2025 PrimeZ.
- `primeZdev/ov-node` — used as the node-side base component.
- `angristan/openvpn-install` — used by the node bootstrap/profile workflow and pinned by commit in `manifest.json`.
- `qrcode-generator` (Kazuhiko Arase) — MIT License — vendored unmodified at `frontend/sub_clients/qr/qrcode.js` and served same-origin for the subscription page QR codes (Copyright (c) 2009 Kazuhiko Arase, http://www.d-project.com/).

The original MIT copyright notice is retained in this repository's `LICENSE` file. PVNetwork modifications, operational tooling, documentation and distribution logic are maintained by DashSaman.

Third-party OpenVPN clients exposed by a deployment are distributed by their respective publishers and remain subject to their own licenses. They are not vendored into this repository.
