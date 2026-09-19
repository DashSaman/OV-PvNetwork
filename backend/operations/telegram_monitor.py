import asyncio
import json
import os
import socket
import ssl
import time
import urllib.parse
import urllib.request
from pathlib import Path

from backend.db.engine import SessionLocal
from backend.db.models import MonitoringSettings
from backend.monitoring_crypto import decrypt_secret
from backend.node.health import build_nodes_health
from backend.operations.alert_transitions import (
    build_node_status_alerts,
    build_transition_messages,
)

STATE = Path('/var/lib/ov-panel/monitor-state.json')


def send(token, chat_id, message):
    data = urllib.parse.urlencode({'chat_id': chat_id, 'text': message}).encode()
    request = urllib.request.Request(
        f'https://api.telegram.org/bot{token}/sendMessage',
        data=data,
        method='POST',
    )
    urllib.request.urlopen(request, timeout=15).read()


# Public helper shared by the scheduled user notifier.
send_telegram = send


def ssl_days(host, port):
    context = ssl.create_default_context()
    with socket.create_connection((host, port), timeout=10) as sock:
        with context.wrap_socket(sock, server_hostname=host) as tls_sock:
            expires_at = ssl.cert_time_to_seconds(tls_sock.getpeercert()['notAfter'])
    return int((expires_at - time.time()) / 86400)



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

    alerts = build_node_status_alerts(nodes, enabled=node_status_alerts_enabled)
    stat = os.statvfs('/')
    used = round(100 * (1 - stat.f_bavail / stat.f_blocks), 1)
    if used >= disk:
        alerts['panel:disk'] = f'⚠️ PVNetwork Panel disk usage: {used}%'

    for node in nodes:
        node_id = node.get('id')
        name = node.get('name') or f'Node {node_id}'
        reasons = node.get('health_reason') or []
        if node.get('cpu_usage') is not None and float(node['cpu_usage']) >= cpu:
            alerts[f'n:{node_id}:cpu'] = f'⚠️ High CPU: {name} — {float(node["cpu_usage"]):.1f}%'
        if node.get('memory_usage') is not None and float(node['memory_usage']) >= ram:
            alerts[f'n:{node_id}:ram'] = f'⚠️ High RAM: {name} — {float(node["memory_usage"]):.1f}%'
        if 'node_api_unreachable' in reasons:
            alerts[f'n:{node_id}:sync'] = f'🔴 Sync unavailable: {name}'

    if host:
        try:
            left = ssl_days(host, port)
            if left <= days:
                alerts['ssl'] = f'⚠️ SSL for {host} expires in {left} day(s)'
        except Exception as exc:
            alerts['ssl'] = f'🔴 SSL check failed for {host}: {type(exc).__name__}'

    try:
        old = json.loads(STATE.read_text()).get('alerts', {})
    except Exception:
        old = {}

    for message in build_transition_messages(old, alerts):
        send(token, chat, message)

    tmp = STATE.with_suffix('.tmp')
    tmp.write_text(
        json.dumps({'checked_at': int(time.time()), 'alerts': alerts}, ensure_ascii=False)
    )
    tmp.replace(STATE)


if __name__ == '__main__':
    asyncio.run(main())
