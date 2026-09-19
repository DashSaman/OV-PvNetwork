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
