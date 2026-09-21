"""Асинхронная работа с SQLite (aiosqlite)."""
import aiosqlite
import hashlib
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Tuple

import config
from models import Channel, Giveaway, RequiredChannel


async def init_db() -> None:
    """Создаёт таблицы, если их нет."""
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS channels (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                username TEXT,
                last_checked_at TIMESTAMP,
                scan_cooldown_hours INTEGER DEFAULT 6,
                is_active INTEGER DEFAULT 1
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS giveaways (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id TEXT NOT NULL,
                message_id INTEGER NOT NULL,
                posted_at TIMESTAMP NOT NULL,
                end_date TIMESTAMP,
                text_hash TEXT NOT NULL DEFAULT '',
                is_forwarded INTEGER DEFAULT 0,
                status TEXT DEFAULT 'active',
                forwarded_msg_id INTEGER,
                UNIQUE(channel_id, message_id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS required_channels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                giveaway_id INTEGER NOT NULL,
                username TEXT NOT NULL,
                subscribed INTEGER DEFAULT 0,
                subscribed_at TIMESTAMP,
                UNIQUE(giveaway_id, username)
            )
        """)
        await db.commit()


# ── Channels ────────────────────────────────────────────────

async def add_or_update_channel(channel: Channel) -> None:
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute("""
            INSERT INTO channels (id, title, username, last_checked_at, scan_cooldown_hours, is_active)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                title = excluded.title,
                username = COALESCE(excluded.username, channels.username),
                last_checked_at = COALESCE(excluded.last_checked_at, channels.last_checked_at),
                is_active = excluded.is_active
        """, (
            channel.id, channel.title, channel.username,
            _to_iso(channel.last_checked_at), channel.scan_cooldown_hours,
            int(channel.is_active)
        ))
        await db.commit()


async def get_channels_to_scan() -> List[Channel]:
    """Возвращает каналы, у которых last_checked_at NULL или прошло больше cooldown."""
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cutoff = datetime.now(timezone.utc) - timedelta(hours=config.COOLDOWN_HOURS)
        rows = await db.execute(
            """SELECT * FROM channels
               WHERE is_active = 1
                 AND (last_checked_at IS NULL OR last_checked_at < ?)
               ORDER BY last_checked_at ASC NULLS FIRST""",
            (_to_iso(cutoff),)
        )
        return [_row_to_channel(r) async for r in rows]


async def update_last_checked(channel_id: str) -> None:
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(
            "UPDATE channels SET last_checked_at = ? WHERE id = ?",
            (_to_iso(datetime.now(timezone.utc)), channel_id)
        )
        await db.commit()


async def deactivate_channel(channel_id: str) -> None:
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(
            "UPDATE channels SET is_active = 0 WHERE id = ?", (channel_id,)
        )
        await db.commit()


# ── Giveaways ─────────────────────────────────────────────

async def giveaway_exists(channel_id: str, message_id: int) -> bool:
    async with aiosqlite.connect(config.DB_PATH) as db:
        cur = await db.execute(
            "SELECT 1 FROM giveaways WHERE channel_id = ? AND message_id = ?",
            (channel_id, message_id)
        )
        return await cur.fetchone() is not None


async def add_giveaway(gw: Giveaway) -> int:
    async with aiosqlite.connect(config.DB_PATH) as db:
        cur = await db.execute("""
            INSERT INTO giveaways (channel_id, message_id, posted_at, end_date, text_hash, is_forwarded, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(channel_id, message_id) DO UPDATE SET
                end_date = COALESCE(excluded.end_date, giveaways.end_date),
                text_hash = excluded.text_hash,
                is_forwarded = excluded.is_forwarded
            RETURNING id
        """, (
            gw.channel_id, gw.message_id, _to_iso(gw.posted_at),
            _to_iso(gw.end_date), gw.text_hash, int(gw.is_forwarded), gw.status
        ))
        row = await cur.fetchone()
        await db.commit()
        return row[0]


async def get_active_giveaways_to_forward() -> List[Tuple[int, Giveaway]]:
    """Возвращает (db_id, Giveaway) для активных, ещё не пересланных."""
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        rows = await db.execute("""
            SELECT * FROM giveaways
            WHERE status = 'active'
              AND forwarded_msg_id IS NULL
              AND (end_date IS NULL OR end_date > ?)
        """, (_to_iso(datetime.now(timezone.utc) - timedelta(days=1)),))
        result = []
        async for r in rows:
            gw = Giveaway(
                channel_id=r["channel_id"],
                message_id=r["message_id"],
                posted_at=_from_iso(r["posted_at"]),
                end_date=_from_iso(r["end_date"]),
                text_hash=r["text_hash"],
                is_forwarded=bool(r["is_forwarded"]),
                status=r["status"],
                forwarded_msg_id=r["forwarded_msg_id"]
            )
            result.append((r["id"], gw))
        return result


async def update_giveaway_forwarded(db_id: int, forwarded_msg_id: int) -> None:
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(
            """UPDATE giveaways
               SET forwarded_msg_id = ?, status = 'forwarded'
               WHERE id = ?""",
            (forwarded_msg_id, db_id)
        )
        await db.commit()


async def mark_giveaways_completed() -> None:
    """Помечает завершёнными те, у кого end_date прошёл более суток назад."""
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(
            """UPDATE giveaways
               SET status = 'completed'
               WHERE status = 'active'
                 AND end_date IS NOT NULL
                 AND end_date < ?""",
            (_to_iso(datetime.now(timezone.utc) - timedelta(days=1)),)
        )
        await db.commit()


# ── Required Channels ─────────────────────────────────────

async def add_required_channel(req: RequiredChannel) -> None:
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute("""
            INSERT OR IGNORE INTO required_channels (giveaway_id, username, subscribed, subscribed_at)
            VALUES (?, ?, ?, ?)
        """, (req.giveaway_id, req.username, req.subscribed, _to_iso(req.subscribed_at)))
        await db.commit()


async def get_pending_subscriptions() -> List[Tuple[int, str]]:
    """Возвращает (giveaway_id, username) для подписки."""
    async with aiosqlite.connect(config.DB_PATH) as db:
        rows = await db.execute(
            "SELECT giveaway_id, username FROM required_channels WHERE subscribed = 0"
        )
        return [(r[0], r[1]) async for r in rows]


async def mark_subscribed(giveaway_id: int, username: str, success: bool = True) -> None:
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(
            """UPDATE required_channels
               SET subscribed = ?, subscribed_at = ?
               WHERE giveaway_id = ? AND username = ?""",
            (1 if success else -1, _to_iso(datetime.now(timezone.utc)), giveaway_id, username)
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
        last_checked_at=_from_iso(r["last_checked_at"]),
        scan_cooldown_hours=r["scan_cooldown_hours"],
        is_active=bool(r["is_active"])
    )


def compute_text_hash(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()[:16]
