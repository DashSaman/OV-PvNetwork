# v1.0.46 candidate — PVN-1030

Reseller live-rate and dashboard responses now project customer UUIDs to the
current owner, including when the dashboard uses a main-admin-populated cache.
Main-admin visibility and the reseller dashboard remain available.

User detail GET requests are read-only. Integrations that used GET to reset usage
must switch to `POST /api/users/{uuid}/reset` with `users:write`. Both Web reset
actions use that route. CLI selected-user diagnostics use the distinct
`GET /api/users/{uuid}/sessions` route, which fails closed against older backends.
Reset baseline accounting, unlimited renewal and mutation locks are preserved.

Web Push registration and both delivery paths share an approved-origin transport.
Google FCM, Mozilla's production endpoint and Apple/Windows push subdomains are
supported; operators can configure additional exact HTTPS origins using
`PUSH_ALLOWED_ORIGINS` in the private panel environment. Origins have no path,
query or credentials. All resolved IPs must be public; the connection pins a
validated IP while verifying the original TLS hostname. Redirects, environment
proxies, automatic retries and unbounded response reads are disabled. Stored
subscriptions are checked again before sending. Unexpected provider endpoints
fail explicitly instead of being used as arbitrary network destinations.

The single public test route reserves a per-user one-hour budget atomically before
delivery, including failed delivery. Changing or re-registering an endpoint does
not reset that budget. Delivery runs outside the ASGI event loop with at most four
concurrent test deliveries per process. An additive compatibility table supports
both SQLite and PostgreSQL without requiring the old optional `last_test_at`
subscription column. Sender logs omit bearer UUIDs and raw provider errors.

Validation includes real ASGI authorization/ownership tests, cache isolation,
SQLite and PostgreSQL reservation races, actual Web Push encryption/VAPID with a
controlled transport, ordinary reset/renewal controls and browser regression.
Exact-commit CI, final public artifact checks and Production deployment remain
separate gates. This candidate is not an approved final public release.

Provider references: [Apple](https://developer.apple.com/documentation/usernotifications/sending-web-push-notifications-in-web-apps-and-browsers),
[Mozilla](https://autopush.readthedocs.io/en/stable/),
[Google](https://firebase.google.com/docs/reference/fcm/rest),
[Microsoft](https://learn.microsoft.com/en-us/windows/apps/develop/notifications/push-notifications/wns-overview).
