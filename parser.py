"""Парсинг текста розыгрышей: ключевые слова, ссылки, даты окончания, фильтрация ботов."""
import re
from datetime import datetime, timezone
from typing import List, Optional

import config
from filter import find_giveaway_dates


def has_inline_buttons(msg) -> bool:
    """Проверяет, есть ли у сообщения inline-кнопки (reply_markup с rows/buttons)."""
    markup = getattr(msg, "reply_markup", None)
    if not markup:
        return False
    rows = getattr(markup, "rows", None)
    if rows:
        for row in rows:
            if getattr(row, "buttons", None):
                return True
    if getattr(markup, "buttons", None):
        return True
    return False


def is_giveaway(text: Optional[str], msg) -> bool:
    """Строгая проверка: нужно И inline-кнопки, И ключевое слово.
    Порядок: сначала проверяем кнопки (быстрее), потом текст."""
    # 1. Сначала проверяем кнопки — это быстрее, чем парсить текст
    if not has_inline_buttons(msg):
        return False
    # 2. Потом проверяем ключевые слова
    if not text:
        return False
    lowered = text.lower()
    return any(kw in lowered for kw in config.GIVEAWAY_KEYWORDS)


def is_forwarded_giveaway(msg) -> bool:
    """True если сообщение — репост (forward)."""
    return getattr(msg, "forward", None) is not None


def extract_channel_links(text: Optional[str]) -> List[str]:
    """Извлекает @username КАНАЛОВ из текста, исключая системные и ботов."""
    if not text:
        return []

    patterns = [
        r'https?://t\.me/s/([a-zA-Z0-9_]{5,32})',
        r'https?://t\.me/([a-zA-Z0-9_]{5,32})',
        r'@([a-zA-Z0-9_]{5,32})',
    ]

    found = set()
    for pat in patterns:
        for match in re.findall(pat, text):
            uname = match.lower().lstrip("@")
            if uname in config.USERNAME_BLACKLIST:
                continue
            if uname.endswith("_bot"):
                continue
            if uname.endswith("bot") and not uname.endswith("abot"):
                continue
            if len(uname) <= 3:
                continue
            found.add(uname)

    return sorted(found)


def extract_end_date(text: Optional[str]) -> Optional[datetime]:
    """Возвращает самую позднюю дату из текста (предположительно дата итогов)."""
    if not text:
        return None
    dates = find_giveaway_dates(text)
    if not dates:
        return None
    latest = max(dates, key=lambda x: x[0])[0]
    if latest.tzinfo is None:
        latest = latest.replace(tzinfo=timezone.utc)
    return latest
