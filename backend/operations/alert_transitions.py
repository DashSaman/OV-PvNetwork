def build_node_status_alerts(nodes, enabled=True):
    if not enabled:
        return {}

    alerts = {}
    for node in nodes:
        node_id = node.get("id")
        name = node.get("name") or f"Node {node_id}"
        if node.get("health") == "offline":
            alerts[f"n:{node_id}:down"] = f"🔴 Node DOWN: {name}"
    return alerts


def threshold_alert_active(
    key,
    value,
    limit,
    was_active,
    counters,
    *,
    raise_samples=2,
    clear_samples=2,
    clear_margin=5.0,
):
    """Debounce noisy threshold alerts and add hysteresis on recovery."""
    bucket = counters.setdefault(key, {"high": 0, "clear": 0})
    high = max(0, int(bucket.get("high", 0) or 0))
    clear = max(0, int(bucket.get("clear", 0) or 0))
    value = float(value)
    limit = float(limit)

    if value >= limit:
        high += 1
        clear = 0
        active = bool(was_active) or high >= max(1, int(raise_samples))
    elif was_active:
        high = 0
        clear_at = max(0.0, limit - float(clear_margin))
        if value < clear_at:
            clear += 1
        else:
            clear = 0
        active = clear < max(1, int(clear_samples))
    else:
        high = 0
        clear = 0
        active = False

    bucket["high"] = high
    bucket["clear"] = clear
    return active


def build_transition_messages(old_alerts, current_alerts):
    messages = []

    for key, message in current_alerts.items():
        if old_alerts.get(key) != message:
            messages.append(message)

    for key, old_message in old_alerts.items():
        if key in current_alerts:
            continue
        if (
            key.startswith("n:")
            and key.endswith(":down")
            and old_message.startswith("🔴 Node DOWN: ")
        ):
            messages.append("🟢 Node UP: " + old_message.removeprefix("🔴 Node DOWN: "))
        else:
            messages.append("✅ Resolved: " + old_message)

    return messages
