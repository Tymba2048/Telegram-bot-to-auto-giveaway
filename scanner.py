"""Сканирование каналов: закреп + последние сообщения.

Мгновенная пересылка розыгрышей в группу.
Дедупликация подписок: не подписываемся дважды на один username.
"""
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Optional, Set

from telethon import TelegramClient
from telethon.tl.functions.channels import GetFullChannelRequest

import config
import database as db
from models import Channel, Giveaway, RequiredChannel
from parser import is_giveaway, is_forwarded_giveaway, extract_channel_links, extract_end_date
from forwarder import forward_giveaway


def normalize_channel_id(cid) -> str:
    cid = str(cid).strip()
    if cid.startswith("-100"):
        return cid
    if cid.startswith("-"):
        cid = cid[1:]
    if not cid.startswith("100"):
        cid = "100" + cid
    return f"-{cid}"


def to_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def is_older_than_max_age(msg_date: datetime) -> bool:
    return to_utc(msg_date) < datetime.now(timezone.utc) - timedelta(days=config.MAX_AGE_DAYS)


async def get_pinned_message(client: TelegramClient, channel):
    """Возвращает закреплённое сообщение или None."""
    try:
        full = await client(GetFullChannelRequest(channel))
        pinned_id = full.full_chat.pinned_msg_id
        if not pinned_id:
            return None
        msg = await client.get_messages(channel, ids=pinned_id)
        return msg
    except Exception as e:
        print(f"    ⚠️ Не удалось получить закреп: {e}")
        return None


async def scan_channel(client: TelegramClient, channel: Channel, subscribed_cache: Set[str]) -> None:
    """Сканирует один канал, находит новые розыгрыши, сразу пересылает."""
    print(f"🔎 Сканируем: {channel.title} ({channel.id})")

    try:
        entity = await client.get_entity(int(channel.id))
    except Exception as e:
        print(f"    ❌ get_entity ошибка: {e}")
        await db.deactivate_channel(channel.id)
        return

    found_any = False

    # ── 1. Закреплённое сообщение ─────────────────────────
    pinned = await get_pinned_message(client, entity)
    if pinned and is_giveaway(pinned.text, pinned):
        if not await db.giveaway_exists(channel.id, pinned.id):
            await _process_giveaway_message(client, channel.id, pinned, subscribed_cache)
            found_any = True

    # ── 2. Последние сообщения (без search=) ─────────────
    async for msg in client.iter_messages(entity, limit=config.SCAN_LIMIT):
        if is_older_than_max_age(msg.date):
            break
        if not is_giveaway(msg.text, msg):
            continue
        if await db.giveaway_exists(channel.id, msg.id):
            continue
        await _process_giveaway_message(client, channel.id, msg, subscribed_cache)
        found_any = True

    if not found_any:
        print(f"    [-] Новых розыгрышей не найдено")

    await db.update_last_checked(channel.id)
    await asyncio.sleep(config.RATE_LIMIT_DELAY)


async def _process_giveaway_message(client, channel_id: str, msg, subscribed_cache: Set[str]) -> None:
    """Добавляет розыгрыш в БД, сразу пересылает, извлекает ссылки, подписывается."""
    is_fwd = is_forwarded_giveaway(msg)
    text_hash = db.compute_text_hash(msg.text or "")
    end_date = extract_end_date(msg.text)

    gw = Giveaway(
        channel_id=channel_id,
        message_id=msg.id,
        posted_at=to_utc(msg.date),
        end_date=end_date,
        text_hash=text_hash,
        is_forwarded=is_fwd,
        status="active"
    )

    gw_db_id = await db.add_giveaway(gw)
    print(f"    [+] Новый розыгрыш msg={msg.id} (fwd={is_fwd}, db_id={gw_db_id})")

    # === МГНОВЕННАЯ ПЕРЕСЫЛКА ===
    try:
        fwd_id = await forward_giveaway(client, channel_id, msg.id)
        await db.update_giveaway_forwarded(gw_db_id, fwd_id)
    except Exception as e:
        print(f"    ⚠️ Пересылка не удалась: {e}")

    # Если это репост — НЕ подписываемся на каналы из условий
    if is_fwd:
        print(f"    ↪️ Репост — подписки на условия пропущены")
        return

    # Извлекаем каналы из условий
    links = extract_channel_links(msg.text)
    if links:
        print(f"    🔗 Найдены условия: {links}")
        for uname in links:
            if uname in subscribed_cache:
                print(f"    ⏭️ Уже подписаны на {uname} (в этом запуске)")
                continue

            await db.add_required_channel(
                RequiredChannel(giveaway_id=gw_db_id, username=uname)
            )
            success = await _subscribe_single(client, uname)
            if success:
                subscribed_cache.add(uname)
            await db.mark_subscribed(gw_db_id, uname, success=success)


async def _subscribe_single(client: TelegramClient, username: str) -> bool:
    """Подписаться на один канал. Возвращает True при успехе.
    Проверяет, что сущность — канал (broadcast), а не пользователь/бот/группа."""
    from telethon.tl.functions.channels import JoinChannelRequest
    from telethon.errors import FloodWaitError, UserAlreadyParticipantError
    from telethon.tl.types import Channel as TlChannel

    link = f"@{username}"
    try:
        entity = await client.get_entity(link)
        if not isinstance(entity, TlChannel):
            print(f"    ⏭️ {username} — это не канал, пропускаем")
            return False
        if not getattr(entity, "broadcast", False):
            print(f"    ⏭️ {username} — это группа/чат, не канал, пропускаем")
            return False

        await client(JoinChannelRequest(entity))
        print(f"    ✅ Подписались на {username}")
        await asyncio.sleep(config.SUBSCRIPTION_DELAY)
        return True
    except FloodWaitError as e:
        print(f"    ⏳ FloodWait на {e.seconds} сек для {username}")
        await asyncio.sleep(e.seconds)
        try:
            entity = await client.get_entity(link)
            if isinstance(entity, TlChannel) and getattr(entity, "broadcast", False):
                await client(JoinChannelRequest(entity))
                print(f"    ✅ Подписались на {username} (после ожидания)")
                return True
        except Exception as e2:
            print(f"    ❌ Повторная ошибка подписки на {username}: {e2}")
        return False
    except UserAlreadyParticipantError:
        print(f"    ✅ Уже подписаны на {username}")
        return True
    except Exception as e:
        print(f"    ❌ Ошибка подписки на {username}: {type(e).__name__}: {e}")
        return False
