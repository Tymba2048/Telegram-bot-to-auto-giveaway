"""Dataclasses для типизации данных."""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Channel:
    id: str                      # нормализованный -100...
    title: str
    username: Optional[str] = None
    last_checked_at: Optional[datetime] = None
    scan_cooldown_hours: int = 6
    is_active: bool = True


@dataclass
class Giveaway:
    channel_id: str
    message_id: int
    posted_at: datetime
    end_date: Optional[datetime] = None
    text_hash: str = ""
    is_forwarded: bool = False   # True если это репост чужого розыгрыша
    status: str = "active"       # active | completed | forwarded
    forwarded_msg_id: Optional[int] = None


@dataclass
class RequiredChannel:
    giveaway_id: int
    username: str
    subscribed: int = 0          # 0 = не подписан, 1 = подписан, -1 = ошибка
    subscribed_at: Optional[datetime] = None
