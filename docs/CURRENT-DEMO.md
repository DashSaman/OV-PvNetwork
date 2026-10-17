# v1.0.54 candidate Demo walkthrough

These captures use the current build and local synthetic API responses. No Production accounts, traffic, addresses or credentials are included. Persian uses dark mode and English light mode, at 390 and 1440 px. A Demo capture does not prove backend execution or deployment. Older version-labelled captures remain historical evidence.

| Flow | Use | Desktop | Phone |
| --- | --- | --- | --- |
| Dashboard | Review live rates, node reachability and backup/recovery status. | [1440](images/v1.0.54/en/desktop/dashboard.png) | [390](images/v1.0.54/en/mobile/dashboard.png) |
| Users | Find an account and inspect quota, expiry, status and assigned nodes. | [1440](images/v1.0.54/en/desktop/users.png) | [390](images/v1.0.54/en/mobile/users.png) |
| Create user | Choose quota/duration/devices and available target nodes before creating. | [1440](images/v1.0.54/en/desktop/user-create.png) | [390](images/v1.0.54/en/mobile/user-create.png) |
| Quick edit | Edit the existing identity, queue a usage reset if intended, then Apply or Cancel. | [1440](images/v1.0.54/en/desktop/quick-edit.png) | [390](images/v1.0.54/en/mobile/quick-edit.png) |
| Nodes | Inspect health and use the selected node’s actions; drain preserves current sessions. | [1440](images/v1.0.54/en/desktop/nodes.png) | [390](images/v1.0.54/en/mobile/nodes.png) |
| Add node | Choose automatic SSH or manual registration. Verify the SSH fingerprint independently. Fresh installation and explicit adoption have different preconditions. | [1440](images/v1.0.54/en/desktop/node-create.png) | [390](images/v1.0.54/en/mobile/node-create.png) |
| Administrators | Review reseller limits and manage the intended administrator only. | [1440](images/v1.0.54/en/desktop/admins.png) | [390](images/v1.0.54/en/mobile/admins.png) |
| Operations | Select the intended users before bulk actions or ownership transfer. Review the result and audit history. | [1440](images/v1.0.54/en/desktop/operations.png) | [390](images/v1.0.54/en/mobile/operations.png) |
| Security | Review rate/IP policies and 2FA. Save recovery codes privately; give API tokens only required scopes. Panel/credential changes require the current password and a verified completion state. | [1440](images/v1.0.54/en/desktop/security.png) | [390](images/v1.0.54/en/mobile/security.png) |
| Fleet | Select target nodes, verify SSH trust and follow the canary/job result before wider changes. | [1440](images/v1.0.54/en/desktop/fleet.png) | [390](images/v1.0.54/en/mobile/fleet.png) |
| Monitoring | Set thresholds and private notification settings, then test the configured destination. | [1440](images/v1.0.54/en/desktop/monitoring.png) | [390](images/v1.0.54/en/mobile/monitoring.png) |
| Bandwidth | Preview the selected policy and target set before activating it. | [1440](images/v1.0.54/en/desktop/bandwidth.png) | [390](images/v1.0.54/en/mobile/bandwidth.png) |

![Dashboard](images/v1.0.54/en/desktop/dashboard.png)

![Quick edit](images/v1.0.54/en/desktop/quick-edit.png)

![Add node](images/v1.0.54/en/desktop/node-create.png)

For step-by-step instructions use [the illustrated manual](UI-GUIDE.md). For installation and recovery use the [installer](INSTALLER-CANDIDATE.md), [lifecycle](LIFECYCLE-CANDIDATE.md), [node](NODE-CANDIDATE.md), [node archives](NODE-ARCHIVES-CANDIDATE.md) and [CLI](CLI.md) guides. A queued request is acceptance; wait for a successful terminal job result.

Separate layout evidence: 13 languages × two themes × nine widths × three native zoom levels = 6,318 views on candidate 1.0.47. The 108-case quick-edit matrix passed on build 1.0.50. These checks do not certify every translation, contrast or assistive technology. Final release gates remain open.
