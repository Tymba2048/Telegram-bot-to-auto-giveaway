"""Сканирование каналов.

Логика:
- Новый канал: iter_messages с offset_date = 90 дней назад, limit=3000.
- Старый канал: iter_messages с offset_date = last_checked_at, limit=3000.
- Фильтр: есть inline-кнопка = розыгрыш.
- Мгновенная пересылка в группу.
- Сохраняем last_message_id = ID самого старого сообщения из выборки (чтобы
  следующий раз продолжить с него, а не начинать с начала).
"""
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Optional

from telethon import TelegramClient

import config
import database as db
from models import Channel
from parser import is_giveaway, is_forwarded
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


async def scan_channel(client: TelegramClient, channel: Channel) -> None:
    """Сканирует канал: 3000 сообщений, начиная с offset_date."""
    print(f"🔎 Сканируем: {channel.title} ({channel.id})")

    try:
        entity = await client.get_entity(int(channel.id))
    except Exception as e:
        print(f"    ❌ get_entity ошибка: {e}")
        await db.deactivate_channel(channel.id)
        return

    # Определяем offset_date
    if channel.last_checked_at is None:
        offset_date = datetime.now(timezone.utc) - timedelta(days=config.MAX_AGE_DAYS)
        print(f"    🆕 Новый канал — с {offset_date.strftime('%d.%m.%Y')}")
    else:
        offset_date = channel.last_checked_at
        print(f"    📌 Продолжаем с {offset_date.strftime('%d.%m.%Y %H:%M')}")

    found_count = 0
    oldest_id: Optional[int] = None   # самый старый msg.id из выборки
    newest_id: Optional[int] = None   # самый новый msg.id из выборки

    async for msg in client.iter_messages(
        entity,
        limit=3000,
        offset_date=offset_date
    ):
        # iter_messages с offset_date возвращает сообщения ДО/ВОКРУГ этой даты,
        # от новых к старым. Сохраняем границы.
        if newest_id is None:
            newest_id = msg.id
        oldest_id = msg.id

        # Фильтр: есть кнопка = розыгрыш
        if not is_giveaway(msg):
            continue

        # Проверка дубликата
        if await db.giveaway_exists(channel.id, msg.id):
            continue

        # Новый розыгрыш
        found_count += 1
        print(f"    [+] Розыгрыш msg={msg.id}")

        # Мгновенная пересылка
        try:
            fwd_id = await forward_giveaway(client, channel.id, msg.id)
            await db.add_giveaway(channel.id, msg.id, to_utc(msg.date), fwd_id)
        except Exception as e:
            print(f"    ⚠️ Пересылка не удалась: {e}")
            await db.add_giveaway(channel.id, msg.id, to_utc(msg.date), None)

    # Сохраняем прогресс: oldest_id = точка, с которой продолжим следующий раз
    # Если ничего не нашли — всё равно сдвигаемся, чтобы не сканировать те же 3000
    if oldest_id is not None:
        await db.update_channel_state(channel.id, oldest_id)
        print(f"    📌 Сохранён прогресс до msg_id={oldest_id}")
    else:
        print(f"    [-] Нет сообщений для сканирования")

    if found_count:
        print(f"    ✅ Найдено розыгрышей: {found_count}")
    else:
        print(f"    [-] Новых розыгрышей не найдено")

    await asyncio.sleep(config.RATE_LIMIT_DELAY)
