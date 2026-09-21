"""Парсинг: только проверка inline-кнопок."""
from typing import Optional


def has_inline_buttons(msg) -> bool:
    """True если у сообщения есть inline-кнопки."""
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


def is_giveaway(msg) -> bool:
    """Единственный критерий: наличие inline-кнопок."""
    return has_inline_buttons(msg)

