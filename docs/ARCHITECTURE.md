# Architecture

## Control plane

The panel is the source of configuration truth for users, nodes and subscription delivery. It talks to OV-Node APIs over authenticated HTTP from the trusted management network/path.

## Data plane

OpenVPN runs on each node. OV-PvNetwork intentionally separates control-plane restarts from the OpenVPN data plane; routine user/profile operations should not restart OpenVPN.

## Desired state and reconciliation

The production design keeps user-node assignment in the panel database and reconciles physical client state on nodes asynchronously/periodically. This prevents a temporarily unavailable node from blocking panel-side user lifecycle operations.

## Telemetry

Node telemetry uses cumulative kernel NIC counters. Rates must be calculated from counter deltas and the actual elapsed time of each node sample. The production design uses an aggregated dashboard endpoint and per-node timing/rolling windows to avoid false rate spikes caused by cache or browser scheduling.

## Subscription plane

The customer page is separate from admin realtime polling. Its node-load sample is intentionally page-load-oriented to avoid generating continuous polling from every customer browser.

## Optional modules

AnyConnect/session control, bandwidth controls, domain activity, monitoring and fleet operations are modular. A failure in an optional collector must not prevent a new OpenVPN node from becoming usable.
