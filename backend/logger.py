import logging
from collections import deque
from logging.handlers import RotatingFileHandler
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(os.path.dirname(BASE_DIR), "data", "app.log")

os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

logging.basicConfig(
    handlers=[RotatingFileHandler(LOG_FILE, maxBytes=10 * 1024 * 1024,
                                  backupCount=5, encoding="utf-8", delay=True)],
    format="{asctime} - {levelname} - {message}",
    style="{",
    datefmt="%Y-%m-%d %H:%M",
    level=logging.WARNING,
)

logger = logging.getLogger("AppLogger")


def get_10_logs():
    """
    Get the last 10 logs from the log file
    """
    if not os.path.exists(LOG_FILE):
        return []
    with open(LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
        return list(deque(f, maxlen=10))
