"""Конфигурация бота."""
import os
from dotenv import load_dotenv

load_dotenv()

API_ID = 0         # <-- вставь свой API_ID
API_HASH = ""       # <-- вставь свой API_HASH
SESSION_NAME = "telethon_session"
GROUP_ID=-1001234567890

SCAN_LIMIT = int(os.getenv("SCAN_LIMIT", "100"))
MAX_AGE_DAYS = int(os.getenv("MAX_AGE_DAYS", "90"))
RATE_LIMIT_DELAY = float(os.getenv("RATE_LIMIT_DELAY", "1.5"))

DB_PATH = os.getenv("DB_PATH", "giveaways.db")
