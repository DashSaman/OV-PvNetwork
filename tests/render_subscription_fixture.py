from pathlib import Path
import sys

from jinja2 import Environment, FileSystemLoader, select_autoescape

root = Path(__file__).resolve().parents[1]
env = Environment(
    loader=FileSystemLoader(root / "frontend" / "templates"),
    autoescape=select_autoescape(["html"]),
)
template = env.get_template("subscription.html")
context = {
    "name": "demo-user-with-a-very-long-name-1234567890@example.invalid",
    "is_active": True,
    "total": 100 * 1024**3,
    "used": 47 * 1024**3,
    "expiry_date": "2026-12-31",
    "device_limit": 10,
    "ovpn_download_links": {
        "Demo-Europe-Very-Long-Node-Name": "#demo-eu",
        "Demo-USA": "#demo-us",
    },
    "node_health": {
        "Demo-Europe-Very-Long-Node-Name": {
            "recommended": True,
            "online": True,
            "load": 44,
            "mbps": 82,
            "flag": "EU",
            "state": "normal",
            "state_fa": "نیمه‌خلوت",
        },
        "Demo-USA": {
            "recommended": False,
            "online": False,
            "load": 0,
            "mbps": 0,
            "flag": "US",
            "state": "offline",
            "state_fa": "آفلاین",
        },
    },
    "anyconnect": {
        "server": "vpn-demo-with-a-very-long-hostname.example.invalid:443",
        "username": "demo-user-with-a-very-long-name-1234567890",
        "password": "demo-password-not-a-secret-1234567890",
    },
}
out = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/pvnetwork-subscription-fixture.html")
out.write_text(template.render(**context), encoding="utf-8")
print(out)
