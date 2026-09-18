# PVNetwork Panel Roadmap

This roadmap keeps the released `v1.0.0` baseline immutable. New behavior ships only in a new tagged release.

## v1.0.0 — released stable baseline
1. Expired/unlimited user renewal without delete/recreate.
2. Finite renewal modes: preserve, reset and add traffic.
3. Renewal support in Mirza integration.
4. Renewal regression tests.
5. Unlimited Reset Usage starts a new 30-day period from reset date.
6. Sanitized production-derived source archive.
7. One-command fresh panel installer bootstrap.
8. Automatic SSH node deployment from Node Management.
9. SHA-256 release artifact verification.
10. English README.
11. Persian README.
12. English/Persian node installation guide.
13. Illustrated public-safe UI guide.
14. Competitive feature matrix.
15. Public-repository privacy rules and secret-scan report.
16. Semantic release policy.

## v1.0.x — operational hardening / compatible fixes
17. `pvnetwork status` command.
18. `pvnetwork doctor` diagnostics.
19. `pvnetwork backup` command.
20. `pvnetwork update` with automatic pre-update backup.
21. `pvnetwork rollback` command.
22. Migration verification before upgrade.
23. Automated update rollback when health verification fails.
24. Fresh-install CI test on disposable VM/container where practical.
25. End-to-end node auto-deploy test on a disposable VPS.

## v1.1 — user lifecycle and observability
26. Periodic traffic reset: daily/weekly/monthly/custom cycle.
27. Scheduled renewal rules.
28. Multi-stage expiry notifications.
29. Configurable traffic threshold notifications.
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
47. Retry queue for temporarily offline nodes.
48. Node capacity thresholds and admission control.
49. Cost/traffic metadata per node.
50. Automated disaster-recovery restore test.

## v1.2 — enterprise access and policy
51. Granular RBAC permissions beyond role names.
52. OAuth2/OIDC admin authentication.
53. Passkey/WebAuthn admin authentication.
54. LDAP authentication integration.
55. RADIUS authentication/accounting integration.
56. SAML SSO integration.
57. Certificate/Let's Encrypt management from UI.
58. SSL auto-renewal status and alerts in UI.
59. HA deployment guide for the control plane.
60. PostgreSQL HA/backup/replication guide.
61. Route-policy editor for OpenVPN users/groups.
62. Split-tunnel policy UI.
63. Destination policy by user/group.
64. GeoIP/GeoSite rule management where applicable.
65. Import/export users and assignments.
66. Migration utilities from supported third-party panels.
67. Generic provisioning webhook/API templates for billing systems.
68. Telegram management bot, not only monitoring.
69. Additional notification-provider abstraction.
70. Configurable notification templates.

## v2.0 — optional universal VPN/proxy control plane
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
88. User-Agent subscription-format negotiation.
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

Every production-visible behavior change gets a new version, changelog entry and tagged GitHub Release. Existing tags and release assets are immutable.
