# PVNetwork Node

Independent versioned source with authenticated HTTPS, existing node API compatibility, PKI/user lifecycle, accounting, session bridge, domain collector and optional Router/OpenVPN capability. Adoption is being implemented to preserve installed certificates, identities and active OpenVPN.

This is an implementation candidate. Real HTTP/SSH installation and real TLS/TUN/traffic tests have run on owned corrected demo fixtures. Exact final artifact, complete adoption/failure recovery, fleet, OS matrix and release gates remain open. See [evidence and limits](../docs/NODE-CANDIDATE.md). Do not use the old unverified remote installer for this package.

Derived from the MIT-licensed [PrimeZ node source](https://github.com/primeZdev/ov-node/tree/fd540b2acfeeac0031e1cf945fc4599fed8e434a), with PVNetwork compatibility/security extensions. Copyright (c) 2025 PrimeZ. The original full notice is retained in [LICENSE](LICENSE).
