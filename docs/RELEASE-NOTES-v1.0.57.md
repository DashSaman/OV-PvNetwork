# v1.0.57 candidate — PVN-1041

Since v1.0.56, existing dialogs contain keyboard focus and restore it when closed; row/mobile menus support keyboard navigation. Fields, scroll regions, login errors and headings expose stronger semantics. A skip link, visible focus outlines, reduced motion and light-theme contrast corrections improve navigation. Subscription QR uses native modality while retaining the prior escaping and download behavior.

See the [illustrated guide](ACCESSIBILITY.md) and [actual validation scope](VALIDATION-v1.0.57.md). This is a QA candidate, not Stable promotion. Exact CI, immutable publication/bootstrap and Production remain separate gates. No live service, VPN, database, node, firewall or certificate changes occur in this task. Use the existing safe update/backup path for installed panels; never replace an existing installation with Fresh Install.
