"""Пересылка розыгрышей в группу + закрепление даты."""
from datetime import datetime, timezone

from telethon import TelegramClient

import config
import database as db


async def send_and_pin_today_date(client: TelegramClient) -> None:
    """Отправляет дату в группу и закрепляет."""
    today_str = datetime.now(timezone.utc).strftime("%d.%m.%y")
    text = f"📅 Сегодня: {today_str}"
    try:
        msg = await client.send_message(config.GROUP_ID, text)
        await client.pin_message(config.GROUP_ID, msg.id, notify=False)
        print(f"✅ Дата {today_str} отправлена и закреплена")
    except Exception as e:
        print(f"⚠️ Не удалось отправить/закрепить дату: {e}")


async def forward_giveaway(client: TelegramClient, channel_id: str, message_id: int) -> int:
    """Пересылает сообщение в группу. Возвращает ID пересланного сообщения."""
    try:
        # Telethon forward_messages принимает список IDs
        fwd = await client.forward_messages(
            config.GROUP_ID,
            messages=message_id,
            from_peer=int(channel_id)
        )
        # fwd — Message или list[Message]
        if isinstance(fwd, list):
            fwd = fwd[0]
        print(f"    📤 Переслано в группу (msg_id={fwd.id})")
        return fwd.id
    except Exception as e:
        print(f"    ❌ Ошибка пересылки: {e}")
        raise


async def process_forward_queue(client: TelegramClient) -> None:
    """Пересылает все активные розыгрыши, которые ещё не были пересланы."""
    items = await db.get_active_giveaways_to_forward()
    if not items:
        print("📭 Нет розыгрышей для пересылки")
        return

    print(f"📤 Пересылка {len(items)} розыгрышей...")
    for db_id, gw in items:
        try:
            fwd_id = await forward_giveaway(client, gw.channel_id, gw.message_id)
            await db.update_giveaway_forwarded(db_id, fwd_id)
        except Exception:
            # Оставляем статус active, попробуем в следующий раз
            continue
