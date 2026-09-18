# User Renewal

PVNetwork Panel renews an existing account without deleting or recreating its identity.

## Preserved identity
- User UUID
- Username
- Assigned nodes
- Subscription URL
- Existing AnyConnect credential identity

## Renewal modes
- Preserve traffic: extend expiry while keeping current quota and usage.
- Reset traffic: extend expiry and start the current finite quota from zero usage.
- Add traffic: extend expiry and add bytes to the existing finite quota.
- Unlimited accounts: extend expiry only; traffic remains unlimited.

## Expired accounts
Renewal starts from today when the existing expiry is already in the past. Active accounts extend from their current expiry date.

## Unlimited Reset Usage behavior
For unlimited accounts (`total = 0`), the existing **Reset Usage** action also starts a fresh 30-day service cycle from the day the reset is pressed. It resets usage to zero, sets expiry to `today + 30 days`, marks the account active, and re-enables the same identity on assigned nodes. Finite accounts keep their current expiry when Reset Usage is used.

The database stores expiry as a calendar date, so this policy is day-based rather than hour/minute-based.

## OpenVPN profiles
Renewal does not rotate certificates unnecessarily. Existing lazy profile validation remains authoritative: if a downloaded profile is missing or invalid, PVNetwork rebuilds it on demand.

## Node synchronization
After the database renewal succeeds, the panel re-enables the same identity on assigned nodes. An unreachable node is reported through the `node_sync` result and does not cause user identity replacement.

## Resellers
Renewing an unlimited account does not consume another unlimited-account slot because the same account identity is retained. Finite `add` and `reset` operations consume reseller traffic credit according to the bytes newly granted.

## Regression coverage
The renewal test suite verifies both behaviors:
- unlimited Reset Usage => `today + 30 days`
- finite Reset Usage => expiry unchanged
