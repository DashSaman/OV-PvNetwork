# Rendered contrast and node deployment — candidate v1.0.58

[فارسی](MANUAL-ACCESSIBILITY-v1.0.58.fa.md) · [Evidence and limits](VALIDATION-v1.0.58.md) · [Existing keyboard guide](ACCESSIBILITY.md)

This candidate continues QA57's manual-review work. It is not yet a published release or a Production UI activation.

1. Switch between light and dark themes. Navigation, node health, chart labels and form borders now have colors paired with their actual surfaces. The fixed mobile header has an opaque theme background so scrolling content cannot obscure its branding. Download/upload chart lines also differ by dash pattern.
2. Scroll through the Dashboard's backup section and populated node-health tables. Backup headings, notices and rows remain readable in the light theme. Each node's weight input has a translated accessible name containing that node's name. Focus the table's scroll region to move horizontally with the keyboard.
3. In **Nodes → Add node**, choose the installation method for the actual server state. A fresh server and an existing node require different operations. Preserve an existing node's name because it forms part of its client certificate identity. [Address-change recovery](incidents/2026-10-18-node-address-change.md).
4. On first SSH contact, verify the host fingerprint through a trusted provider console or an already authenticated channel, then enter it in the fingerprint field. The associated help explains this requirement. A fingerprint merely displayed in an error is not automatically trusted or copied into the field.
5. After submitting an automatic job, focus stays inside a named native deployment dialog. Progress output exposes log semantics; a failure is announced as an alert. **Back to form** returns to a usable form with SSH secrets cleared, including after an HTTP failure. Running jobs retain their dismissal restriction. A completed job can close with the keyboard and returns focus to its original invoker.
6. At 400% browser zoom, the console can scroll vertically to keep its footer reachable. The tests also apply WCAG text-spacing values. Forced-color browser emulation retains system palette adjustment, visible button borders and focus. These checks and synthetic screenshots do not substitute for a real screen reader, speech control or OS hardware session.

![English light-theme deployment error — synthetic local example](images/v1.0.58/deployment-en-light-1440.png)

![Persian mobile deployment error — synthetic local example](images/v1.0.58/deployment-fa-dark-390.png)

All images use synthetic loopback fixtures. They contain no customer information or real server access details. They demonstrate UI states, not an actual installation on a new VPS.

File upload fields use explicit theme colors for both the filename area and **Choose file** button. Their opaque color pairs are checked separately from normal text; the browser's native file-selector painting and OS file picker remain manual-review items.
