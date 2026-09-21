"""Асинхронная SQLite (aiosqlite)."""
import aiosqlite
from datetime import datetime, timezone, timedelta
from typing import List, Optional

import config
from models import Channel


async def init_db() -> None:
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS channels (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                username TEXT,
                last_message_id INTEGER,
                last_checked_at TIMESTAMP,
                is_active INTEGER DEFAULT 1
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS giveaways (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id TEXT NOT NULL,
                message_id INTEGER NOT NULL,
                posted_at TIMESTAMP NOT NULL,
                forwarded_msg_id INTEGER,
                UNIQUE(channel_id, message_id)
            )
        """)
        await db.commit()


# ── Channels ────────────────────────────────────────────────

async def add_or_update_channel(channel: Channel) -> None:
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute("""
            INSERT INTO channels (id, title, username, last_message_id, last_checked_at, is_active)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                title = excluded.title,
                username = COALESCE(excluded.username, channels.username),
                is_active = excluded.is_active
        """, (
            channel.id, channel.title, channel.username,
            channel.last_message_id, _to_iso(channel.last_checked_at),
            int(channel.is_active)
        ))
        await db.commit()


async def get_all_active_channels() -> List[Channel]:
    """Все активные каналы для сканирования."""
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        rows = await db.execute("SELECT * FROM channels WHERE is_active = 1")
        return [_row_to_channel(r) async for r in rows]


async def update_channel_state(channel_id: str, last_message_id: int) -> None:
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(
            "UPDATE channels SET last_message_id = ?, last_checked_at = ? WHERE id = ?",
            (last_message_id, _to_iso(datetime.now(timezone.utc)), channel_id)
        )
        await db.commit()


async def deactivate_channel(channel_id: str) -> None:
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute("UPDATE channels SET is_active = 0 WHERE id = ?", (channel_id,))
        await db.commit()


# ── Giveaways ─────────────────────────────────────────────

async def giveaway_exists(channel_id: str, message_id: int) -> bool:
    async with aiosqlite.connect(config.DB_PATH) as db:
        cur = await db.execute(
            "SELECT 1 FROM giveaways WHERE channel_id = ? AND message_id = ?",
            (channel_id, message_id)
        )
        return await cur.fetchone() is not None


async def add_giveaway(channel_id: str, message_id: int, posted_at: datetime, forwarded_msg_id: Optional[int] = None) -> None:
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute("""
            INSERT OR IGNORE INTO giveaways (channel_id, message_id, posted_at, forwarded_msg_id)
            VALUES (?, ?, ?, ?)
        """, (channel_id, message_id, _to_iso(posted_at), forwarded_msg_id))
        await db.commit()


async def update_forwarded(channel_id: str, message_id: int, forwarded_msg_id: int) -> None:
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(
            "UPDATE giveaways SET forwarded_msg_id = ? WHERE channel_id = ? AND message_id = ?",
            (forwarded_msg_id, channel_id, message_id)
        )
        await db.commit()


# ── Helpers ───────────────────────────────────────────────

def _to_iso(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


def _from_iso(s: Optional[str]) -> Optional[datetime]:
    if s is None:
        return None
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _row_to_channel(r) -> Channel:
    return Channel(
        id=r["id"],
        title=r["title"],
        username=r["username"],
        last_message_id=r["last_message_id"],
        last_checked_at=_from_iso(r["last_checked_at"]),
        is_active=bool(r["is_active"])
    )
