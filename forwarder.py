"""Пересылка розыгрышей в группу + закрепление даты."""
from datetime import datetime, timezone

from telethon import TelegramClient

import config


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
    fwd = await client.forward_messages(
        config.GROUP_ID,
        messages=message_id,
        from_peer=int(channel_id)
    )
    if isinstance(fwd, list):
        fwd = fwd[0]
    print(f"    📤 Переслано в группу (msg_id={fwd.id})")
    return fwd.id
