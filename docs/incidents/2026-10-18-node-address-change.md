# Node address change after deleting its panel entry

Task: **PVN-1043**. Status: verified Production operation; application version unchanged.

The automatic installer stopped at SSH host-key verification. The replacement address belonged to the same existing node: its host key matched previously trusted key material, while its API credential and certificate identity matched a verified historical backup. A fresh installation would have conflicted with existing VPN and unrelated services.

The recovery preserved the original node name because client certificate names include it. After a fresh native backup and successful database restore rehearsal, the existing-service path of the panel API registered the node without applying new remote settings. Only its exact historical user memberships were restored. Current counters from a complete OpenVPN management response supplied usage baselines; memberships, baselines and activation committed together while accounting readers were briefly excluded. Shared usage totals, quotas, expiry dates and device settings were retained. Traffic during the unregistered interval was not reconstructed or retrospectively charged.

An initial verification helper could not compare nullable historical usage values. Its narrow rollback removed only the newly created, unchanged registration and verified the original state. After correcting that check, the recovery and two subsequent API/public-health samples passed. A new SSH connection succeeded using the saved verified host key. Target and controller service PIDs/restart counts, protected configuration, CA, client template and existing certificates were preserved. No VPN or unrelated service restarted. An external VPN-client connection remains untested.

Private credentials, addresses, client identifiers, database copies and recovery journals are kept outside the public repository.

For a new empty server, supply its SSH fingerprint only after checking it through a trusted provider console or an already authenticated channel. An observed fingerprint in an error message alone is insufficient. For an existing server with a changed address, preserve its node name and existing credentials. If its panel entry was already deleted, recover exact memberships and live accounting baselines from verified evidence before enabling it; do not treat it as a fresh installation.

[فارسی](2026-10-18-node-address-change.fa.md)
