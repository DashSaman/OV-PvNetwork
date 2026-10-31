import logging
from logging.handlers import RotatingFileHandler
import os

from core.config import settings

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(os.path.dirname(BASE_DIR), "data", "app.log")

os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

logging.basicConfig(
    handlers=[RotatingFileHandler(LOG_FILE, maxBytes=10 * 1024 * 1024,
                                  backupCount=5, encoding="utf-8", delay=True)],
    format="{asctime} - {levelname} - {message}",
    style="{",
    datefmt="%Y-%m-%d %H:%M",
    level=settings.debug,
)

logger = logging.getLogger("AppLogger")
