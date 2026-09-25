import asyncio
import json
import os
import socket
import ssl
import time
import requests
from pathlib import Path

from backend.db.engine import SessionLocal
from backend.db.models import MonitoringSettings
from backend.monitoring_crypto import decrypt_secret
from backend.node.health import build_nodes_health
from backend.operations.alert_transitions import (
    build_node_status_alerts,
    build_transition_messages,
    threshold_alert_active,
)
from backend.operations.renewal_alerts import (
    build_renewal_alerts,
    build_renewal_transition_messages,
)

STATE = Path('/var/lib/pvnetwork-panel/monitor-state.json')


def send(token, chat_id, message):
    response = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data={"chat_id": chat_id, "text": message},
        timeout=15,
    )
    response.raise_for_status()


# Public helper shared by the scheduled user notifier.
send_telegram = send


def ssl_days(host, port):
    context = ssl.create_default_context()
    with socket.create_connection((host, port), timeout=10) as sock:
        with context.wrap_socket(sock, server_hostname=host) as tls_sock:
            expires_at = ssl.cert_time_to_seconds(tls_sock.getpeercert()['notAfter'])
    return int((expires_at - time.time()) / 86400)


def _load_state():
    try:
        value = json.loads(STATE.read_text())
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


async def main():
    db = SessionLocal()
    try:
        cfg = db.query(MonitoringSettings).filter(MonitoringSettings.id == 1).first()
        if not cfg or not cfg.enabled:
            return
        token = decrypt_secret(cfg.telegram_token_encrypted)
        chat = cfg.telegram_chat_id
        if not token or not chat:
            return
        nodes = await build_nodes_health(db)
        cpu = cfg.cpu_limit
        ram = cfg.ram_limit
        disk = cfg.disk_limit
        host = cfg.ssl_host
        port = cfg.ssl_port
        days = cfg.ssl_warning_days
        node_status_alerts_enabled = getattr(cfg, 'node_status_alerts', True)
    finally:
        db.close()

    state = _load_state()
    old = state.get('alerts', {})
    if not isinstance(old, dict):
        old = {}
    threshold_counters = state.get('threshold_counters', {})
    if not isinstance(threshold_counters, dict):
        threshold_counters = {}

    alerts = build_node_status_alerts(nodes, enabled=node_status_alerts_enabled)
    stat = os.statvfs('/')
    used = round(100 * (1 - stat.f_bavail / stat.f_blocks), 1)
    if used >= disk:
        alerts['panel:disk'] = f'⚠️ PVNetwork Panel disk usage: {used}%'

    live_cpu_keys = set()
    for node in nodes:
        node_id = node.get('id')
        name = node.get('name') or f'Node {node_id}'
        reasons = node.get('health_reason') or []
        if node.get('cpu_usage') is not None:
            key = f'n:{node_id}:cpu'
            live_cpu_keys.add(key)
            value = float(node['cpu_usage'])
            if threshold_alert_active(
                key,
                value,
                cpu,
                key in old,
                threshold_counters,
                raise_samples=2,
                clear_samples=2,
                clear_margin=5.0,
            ):
                alerts[key] = old.get(key) or f'⚠️ High CPU: {name} — {value:.1f}%'
        if node.get('memory_usage') is not None and float(node['memory_usage']) >= ram:
            alerts[f'n:{node_id}:ram'] = f'⚠️ High RAM: {name} — {float(node["memory_usage"]):.1f}%'
        if 'node_api_unreachable' in reasons:
            alerts[f'n:{node_id}:sync'] = f'🔴 Sync unavailable: {name}'

    for key in list(threshold_counters):
        if key.endswith(':cpu') and key not in live_cpu_keys and key not in old:
            threshold_counters.pop(key, None)

    if host:
        try:
            left = ssl_days(host, port)
            if left <= days:
                alerts['ssl'] = f'⚠️ SSL for {host} expires in {left} day(s)'
        except Exception as exc:
            alerts['ssl'] = f'🔴 SSL check failed for {host}: {type(exc).__name__}'

    # PVN-202/PVN-203: renewal (expiry / traffic-threshold) alerts.
    renewal = {}
    if node_status_alerts_enabled:
        from backend.db.models import User

        users = db.query(User).all()
        renewal = {item.key: item.message for item in build_renewal_alerts(users)}
        alerts.update(renewal)

    # Renewal keys are owned by their own silent-clear transition builder;
    # exclude them from the node-alert transition set so the generic
    # builder never announces them as "Resolved" on every run.
    old_node_alerts = {
        key: message
        for key, message in old.items()
        if not key.startswith("renew:")
    }
    for message in build_transition_messages(old_node_alerts, alerts):
        send(token, chat, message)

    # PVN-1018: one consolidated digest per 24h instead of bursts.
    last_digest = int(state.get("renewal_digest_at") or 0)
    if renewal and int(time.time()) - last_digest >= 86400:
        lines = [message for _, message in sorted(renewal.items())][:30]
        digest = "🔔 یادآوری تمدید (خلاصه ۲۴ ساعته):
" + "
".join(lines)
        send(token, chat, digest)
        state["renewal_digest_at"] = int(time.time())

    tmp = STATE.with_suffix('.tmp')
    tmp.write_text(
        json.dumps(
            {
                'checked_at': int(time.time()),
                'alerts': alerts,
                'threshold_counters': threshold_counters,
                'renewal_digest_at': int(state.get('renewal_digest_at') or 0),
            },
            ensure_ascii=False,
        )
    )
    tmp.replace(STATE)


if __name__ == '__main__':
    asyncio.run(main())
