"""Автоподписка на каналы из условий розыгрышей с защитой от флуда."""
import asyncio
from datetime import datetime, timezone

from telethon import TelegramClient
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.errors import FloodWaitError, InviteHashExpiredError, UserAlreadyParticipantError

import config
import database as db


async def subscribe_single(client: TelegramClient, username: str) -> bool:
    """Подписаться на один канал. Возвращает True при успехе."""
    link = f"@{username}"
    try:
        entity = await client.get_entity(link)
        await client(JoinChannelRequest(entity))
        print(f"    ✅ Подписались на {username}")
        await asyncio.sleep(config.SUBSCRIPTION_DELAY)
        return True
    except FloodWaitError as e:
        print(f"    ⏳ FloodWait на {e.seconds} сек для {username}")
        await asyncio.sleep(e.seconds)
        # Один retry
        try:
            entity = await client.get_entity(link)
            await client(JoinChannelRequest(entity))
            print(f"    ✅ Подписались на {username} (после ожидания)")
            return True
        except Exception as e2:
            print(f"    ❌ Повторная ошибка подписки на {username}: {e2}")
            return False
    except UserAlreadyParticipantError:
        print(f"    ✅ Уже подписаны на {username}")
        return True
    except InviteHashExpiredError:
        print(f"    ❌ Ссылка/инвайт на {username} просрочен")
        return False
    except Exception as e:
        print(f"    ❌ Ошибка подписки на {username}: {type(e).__name__}: {e}")
        return False


async def process_pending_subscriptions(client: TelegramClient) -> None:
    """Обрабатывает все ожидающие подписки из БД."""
    pending = await db.get_pending_subscriptions()
    if not pending:
        return

    print(f"🔄 Обработка {len(pending)} подписок...")
    for gw_id, username in pending:
        success = await subscribe_single(client, username)
        await db.mark_subscribed(gw_id, username, success=success)
