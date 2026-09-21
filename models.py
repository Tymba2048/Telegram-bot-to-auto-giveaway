"""Dataclasses."""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Channel:
    id: str
    title: str
    username: Optional[str] = None
    last_message_id: Optional[int] = None  # последнее проверенное сообщение
    last_checked_at: Optional[datetime] = None
    is_active: bool = True
