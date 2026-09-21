"""Точка входа."""
import asyncio

from telethon import TelegramClient

import config
import database as db
from models import Channel
from scanner import scan_channel, normalize_channel_id
from forwarder import send_and_pin_today_date


async def sync_dialogs(client: TelegramClient) -> None:
    """Добавляет новые каналы из диалогов в БД."""
    print("🔄 Синхронизация диалогов...")
    dialogs = await client.get_dialogs()
    added = 0
    for d in dialogs:
        if not d.is_channel:
            continue
        entity = d.entity
        if getattr(entity, "broadcast", False) is not True:
            continue

        cid = normalize_channel_id(entity.id)
        username = getattr(entity, "username", None)
        ch = Channel(
            id=cid,
            title=getattr(entity, "title", "Unknown"),
            username=username,
            is_active=True
        )
        await db.add_or_update_channel(ch)
        added += 1
    print(f"   Синхронизировано каналов: {added}")


async def main() -> None:
    if not config.API_ID or not config.API_HASH:
        raise ValueError("API_ID и API_HASH должны быть заданы")
    if not config.GROUP_ID:
        raise ValueError("GROUP_ID должен быть задан")

    await db.init_db()

    async with TelegramClient(config.SESSION_NAME, config.API_ID, config.API_HASH) as client:
        await send_and_pin_today_date(client)
        await sync_dialogs(client)

        channels = await db.get_all_active_channels()
        print(f"🔍 К сканированию: {len(channels)} каналов")

        for ch in channels:
            await scan_channel(client, ch)

        print("🏁 Цикл завершён")


if __name__ == "__main__":
    asyncio.run(main())
