"""Копирование всех сообщений из группы в файл Primeri_giveaways.
Сохраняет полный объект Message (текст, реакции, ссылки, кнопки, медиа, forward и т.д.).
"""
import asyncio
import pickle
import json
from datetime import datetime, timezone

from telethon import TelegramClient
from telethon.tl.types import (
    Message, MessageEntityUrl, MessageEntityTextUrl,
    MessageEntityMention, MessageEntityHashtag,
    ReactionEmoji, ReactionCustomEmoji,
    MessageReactions, ReactionCount
)

# === НАСТРОЙКИ (замени на свои или используй .env) ===
API_ID =  0       # <-- вставь свой API_ID
API_HASH = ""  # <-- вставь свой API_HASH
SESSION_NAME = ""
SOURCE_GROUP_ID = ""
OUTPUT_FILE = "Primeri_giveaways"
# ===================================================


def serialize_message(msg: Message) -> dict:
    """Превращает объект Message в словарь со всеми полями."""
    data = {
        "id": msg.id,
        "date": msg.date.isoformat() if msg.date else None,
        "text": msg.text or "",
        "raw_text": msg.raw_text or "",
        "message": msg.message or "",
        "out": msg.out,
        "mentioned": msg.mentioned,
        "media_unread": msg.media_unread,
        "silent": msg.silent,
        "post": msg.post,
        "from_scheduled": msg.from_scheduled,
        "legacy": msg.legacy,
        "edit_hide": msg.edit_hide,
        "pinned": msg.pinned,
        "noforwards": msg.noforwards,
        "invert_media": msg.invert_media,
        "views": msg.views,
        "forwards": msg.forwards,
        "edit_date": msg.edit_date.isoformat() if msg.edit_date else None,
        "post_author": msg.post_author,
        "grouped_id": msg.grouped_id,
        "ttl_period": msg.ttl_period,
    }

    # --- Отправитель ---
    if msg.sender_id:
        data["sender_id"] = msg.sender_id
    if msg.sender:
        sender = msg.sender
        data["sender"] = {
            "id": getattr(sender, "id", None),
            "username": getattr(sender, "username", None),
            "first_name": getattr(sender, "first_name", None),
            "last_name": getattr(sender, "last_name", None),
            "title": getattr(sender, "title", None),
            "type": type(sender).__name__,
        }

    # --- Чат ---
    if msg.chat_id:
        data["chat_id"] = msg.chat_id
    if msg.chat:
        chat = msg.chat
        data["chat"] = {
            "id": getattr(chat, "id", None),
            "title": getattr(chat, "title", None),
            "username": getattr(chat, "username", None),
            "type": type(chat).__name__,
        }

    # --- Forward ---
    if msg.forward:
        fwd = msg.forward
        data["forward"] = {
            "from_id": getattr(fwd, "from_id", None),
            "from_name": getattr(fwd, "from_name", None),
            "channel_post": getattr(fwd, "channel_post", None),
            "post_author": getattr(fwd, "post_author", None),
            "date": fwd.date.isoformat() if getattr(fwd, "date", None) else None,
        }

    # --- Медиа ---
    if msg.media:
        media = msg.media
        data["media"] = {
            "type": type(media).__name__,
            "string_repr": str(media)[:500],
        }
        # Попытка извлечь ссылку на медиа
        if hasattr(media, "webpage") and media.webpage:
            wp = media.webpage
            data["media"]["webpage"] = {
                "url": getattr(wp, "url", None),
                "display_url": getattr(wp, "display_url", None),
                "title": getattr(wp, "title", None),
                "description": getattr(wp, "description", None),
            }

    # --- Сущности (ссылки, упоминания, хештеги) ---
    if msg.entities:
        entities = []
        for ent in msg.entities:
            e = {
                "type": type(ent).__name__,
                "offset": ent.offset,
                "length": ent.length,
            }
            if isinstance(ent, MessageEntityUrl):
                e["url"] = msg.text[ent.offset:ent.offset + ent.length]
            elif isinstance(ent, MessageEntityTextUrl):
                e["url"] = ent.url
            elif isinstance(ent, MessageEntityMention):
                e["mention"] = msg.text[ent.offset:ent.offset + ent.length]
            elif isinstance(ent, MessageEntityHashtag):
                e["hashtag"] = msg.text[ent.offset:ent.offset + ent.length]
            entities.append(e)
        data["entities"] = entities

    # --- Кнопки (reply_markup) ---
    if msg.reply_markup:
        markup = msg.reply_markup
        buttons = []
        rows = getattr(markup, "rows", [])
        for row in rows:
            row_buttons = []
            for btn in getattr(row, "buttons", []):
                b = {"type": type(btn).__name__}
                if hasattr(btn, "text"):
                    b["text"] = btn.text
                if hasattr(btn, "url"):
                    b["url"] = btn.url
                if hasattr(btn, "data"):
                    b["data"] = btn.data.hex() if btn.data else None
                if hasattr(btn, "query"):
                    b["query"] = btn.query
                row_buttons.append(b)
            buttons.append(row_buttons)
        data["reply_markup"] = buttons

    # --- Реакции ---
    if msg.reactions:
        reactions = []
        for react in msg.reactions.results:
            r = {"count": react.count}
            if isinstance(react.reaction, ReactionEmoji):
                r["emoji"] = react.reaction.emoticon
            elif isinstance(react.reaction, ReactionCustomEmoji):
                r["custom_emoji_id"] = react.reaction.document_id
            reactions.append(r)
        data["reactions"] = reactions
        data["reactions_can_add"] = msg.reactions.can_add_list

    # --- Reply ---
    if msg.reply_to:
        data["reply_to_msg_id"] = getattr(msg.reply_to, "reply_to_msg_id", None)

    # --- Файлы (document/photo) ---
    if msg.file:
        data["file"] = {
            "name": getattr(msg.file, "name", None),
            "ext": getattr(msg.file, "ext", None),
            "mime_type": getattr(msg.file, "mime_type", None),
            "size": getattr(msg.file, "size", None),
        }

    return data


async def dump_messages():
    if not API_ID or not API_HASH:
        print("❌ Заполни API_ID и API_HASH в начале файла")
        return

    async with TelegramClient(SESSION_NAME, API_ID, API_HASH) as client:
        print(f"📥 Читаем сообщения из группы {SOURCE_GROUP_ID}...")

        messages = []
        count = 0
        async for msg in client.iter_messages(SOURCE_GROUP_ID, limit=None):
            if not isinstance(msg, Message):
                continue
            data = serialize_message(msg)
            messages.append(data)
            count += 1
            if count % 100 == 0:
                print(f"   Прочитано: {count} сообщений...")

        print(f"✅ Всего прочитано: {count} сообщений")

        # Сохраняем в pickle (полные объекты можно восстановить)
        with open(OUTPUT_FILE + ".pkl", "wb") as f:
            pickle.dump(messages, f)
        print(f"💾 Сохранено в {OUTPUT_FILE}.pkl (pickle, полные объекты)")

        # Сохраняем в JSON (читаемый формат)
        with open(OUTPUT_FILE + ".json", "w", encoding="utf-8") as f:
            json.dump(messages, f, ensure_ascii=False, indent=2)
        print(f"💾 Сохранено в {OUTPUT_FILE}.json (читаемый JSON)")

        # Сохраняем текстовый дамп для быстрого просмотра
        with open(OUTPUT_FILE + ".txt", "w", encoding="utf-8") as f:
            for m in messages:
                f.write(f"[{m['id']}] {m['date']}\n")
                f.write(f"Text: {m['text'][:500]}\n")
                if m.get("reply_markup"):
                    f.write(f"Buttons: {json.dumps(m['reply_markup'], ensure_ascii=False)}\n")
                if m.get("reactions"):
                    f.write(f"Reactions: {json.dumps(m['reactions'], ensure_ascii=False)}\n")
                if m.get("forward"):
                    f.write(f"Forward: {json.dumps(m['forward'], ensure_ascii=False)}\n")
                f.write("-" * 50 + "\n")
        print(f"💾 Сохранено в {OUTPUT_FILE}.txt (текстовый обзор)")


if __name__ == "__main__":
    asyncio.run(dump_messages())
