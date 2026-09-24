# PVNetwork Panel v1.0.17 — Debounced CPU Threshold Alerts

`PVN-1000` stabilizes the live-Production CPU threshold alerting that previously flapped on transient spikes.

## Problem
A node CPU sample crossing the configured threshold for a single monitoring tick fired an immediate High CPU alert, and a single sample dipping back under the threshold fired an immediate Resolved message. Transient spikes therefore produced rapid alert/resolve Telegram message storms, unnecessary monitoring churn and noisy operations channels while other services were busy.

## Fix
- High CPU now requires `2` consecutive at-threshold samples before the alert fires.
- Resolved now requires `2` consecutive below-threshold samples with a strict `5.0` percentage-point recovery margin, so a sample oscillating just under the threshold cannot clear an active alert.
- Active alert text is reused from persisted state so the original message (including the captured percentage) is not rewritten mid-incident.
- Threshold state (`alerts`) and per-key consecutive-sample counters (`threshold_counters`) persist in the monitor state file across monitor restarts; a restart cannot re-announce an already-active alert.
- CPU counters for nodes that stop reporting (key neither live nor active) are dropped, preventing stale counters from arming future instant alerts.

## Scope and safety
RAM, disk, sync-availability, SSL and Node DOWN/UP transition alerts keep their existing semantics. No OpenVPN listener, Node service, Router compatibility listener, profile, certificate, routing, firewall or active VPN-session behavior is changed by this patch. The panel backend service itself does not require a restart beyond the normal release deployment.

## Release gate
Exact-head CI, verified rollback backup, narrow deployment, local/public health verification, post-deploy log review, sanitized artifact plus SHA256 publish and public re-download verification.
