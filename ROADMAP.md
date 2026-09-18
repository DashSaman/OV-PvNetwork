# PVNetwork Panel Roadmap

This roadmap separates **core OpenVPN/AnyConnect product needs** from optional **universal proxy/Xray expansion**. Priorities are based on production safety, operator needs, user experience, maintainability, and gaps observed in Marzban, 3X-UI, Hiddify Manager, Remnawave, OpenVPN Access Server, and Pritunl.

## v1.0.0 — Stable baseline blockers
1. Expired/unlimited user renewal without delete/recreate.
2. Finite renewal modes: preserve, reset, add traffic.
3. Renewal support in Mirza integration.
4. Renewal regression tests and audit visibility.
5. Production-safe main-panel installer.
6. Production-safe node installer.
7. `pvnetwork status` command.
8. `pvnetwork doctor` diagnostics.
9. `pvnetwork update` with pre-update backup.
10. `pvnetwork backup` command.
11. `pvnetwork rollback` command.
12. `pvnetwork version` command.
13. Installer/update dry-run tests.
14. Migration verification before upgrade.
15. Stable/beta release channel policy.
16. SHA256 checksums for release artifacts.
17. English README.
18. Persian README.
19. English/Persian installation guide.
20. English/Persian node installation guide.
21. English/Persian update/rollback guide.
22. English/Persian admin/user guide.
23. Sanitized screenshots for all major pages/actions.
24. CHANGELOG and SemVer release policy.
25. GitHub Release v1.0.0 with known issues and compatibility notes.

## v1.1 — Operations, user lifecycle and observability
26. Periodic traffic reset: daily/weekly/monthly/custom cycle.
27. Scheduled renewal rules.
28. Multi-stage expiry notifications.
29. Traffic threshold notifications at configurable percentages.
30. Generic outbound webhooks for user/node/quota/expiry events.
31. Prometheus metrics endpoint.
32. Official Grafana dashboard.
33. Long-term node traffic history.
34. Long-term per-user traffic history with configurable retention.
35. Top users/top nodes analytics.
36. CSV report export.
37. Excel report export.
38. Central log viewer.
39. Downloadable sanitized support/diagnostic bundle.
40. Device inventory per user.
41. Revoke device/session action.
42. HWID/device-limit option in addition to session limits.
43. Self-service user portal improvements.
44. QR codes for applicable connection outputs.
45. PWA admin installation.
46. Background job queue for slow node operations.
47. Operation retry queue for temporarily offline nodes.
48. Node capacity thresholds and admission control.
49. Cost/traffic metadata per node.
50. Automated disaster-recovery restore test.

## v1.2 — Enterprise access and policy
51. Granular RBAC permissions beyond role names.
52. OAuth2/OIDC admin authentication.
53. Passkey/WebAuthn admin authentication.
54. LDAP authentication integration.
55. RADIUS authentication/accounting integration.
56. SAML SSO integration.
57. Certificate/Let's Encrypt management from UI.
58. SSL auto-renewal status and alerts in UI.
59. HA deployment guide for control plane.
60. PostgreSQL HA/backup/replication guide.
61. Route-policy editor for OpenVPN users/groups.
62. Split-tunnel policy UI.
63. Destination policy by user/group.
64. GeoIP/GeoSite rule management where applicable.
65. Import/export users and assignments.
66. Migration utilities from supported third-party panels.
67. Generic provisioning webhook/API templates for billing systems.
68. Telegram management bot, not only monitoring.
69. Discord/other notification provider abstraction.
70. Configurable notification templates.

## v2.0 — Optional universal VPN/proxy control plane
71. WireGuard core integration.
72. Xray core integration.
73. VLESS support.
74. VMess support.
75. Trojan support.
76. Shadowsocks support.
77. REALITY support.
78. Hysteria2 support.
79. TUIC support.
80. Sing-box integration.
81. Host abstraction independent of physical node.
82. Reusable config-profile abstraction.
83. Multi-protocol identity under one user.
84. Raw/Base64 subscription output.
85. Xray JSON subscription output.
86. Sing-box subscription output.
87. Clash/Mihomo subscription output.
88. User-Agent based subscription format negotiation.
89. Subscription template editor.
90. Subscription response rules.
91. WARP outbound support.
92. Custom outbound pools.
93. Outbound proxy chaining.
94. Load balancers and failover rules.
95. Routing rules import/export.
96. Built-in geosite/geoip updates.
97. Multi-inbound/single-port fallback configuration.
98. Protocol-aware traffic analytics.
99. Protocol-aware node capability negotiation.
100. Migration assistant from Xray-oriented panels.

## Release rule
Every production-visible feature or behavior change must update VERSION/CHANGELOG as appropriate and ship through a tagged GitHub Release. Patch releases are fixes, minor releases add backwards-compatible capabilities, and major releases may contain breaking architecture or protocol changes.