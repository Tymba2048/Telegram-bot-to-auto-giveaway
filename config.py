"""Конфигурация бота. Приоритет: переменные окружения → значения по умолчанию."""
import os
from dotenv import load_dotenv

load_dotenv()

# Telethon
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
SESSION_NAME = os.getenv("SESSION_NAME", "giveaway_session")

# Целевая группа для пересылки розыгрышей
GROUP_ID = int(os.getenv("GROUP_ID", "0"))

# Поведение
COOLDOWN_HOURS = int(os.getenv("COOLDOWN_HOURS", "6"))          # минимум часов между проверками одного канала
SCAN_LIMIT = int(os.getenv("SCAN_LIMIT", "100"))                # сколько сообщений читать сверху
MAX_AGE_DAYS = int(os.getenv("MAX_AGE_DAYS", "90"))             # не читать сообщения старше N дней
RATE_LIMIT_DELAY = float(os.getenv("RATE_LIMIT_DELAY", "1.5"))  # задержка между каналами (сек)
SUBSCRIPTION_DELAY = float(os.getenv("SUBSCRIPTION_DELAY", "2.0"))  # задержка между подписками (сек)

# Ключевые слова для определения розыгрыша (регистр не важен).
# Оставлены только надёжные: "приз" убран, т.к. ловит "признание/признак";
# "win" убран, т.к. ловит "Windows"; "итоги" убрано, т.к. слишком общее.
GIVEAWAY_KEYWORDS = [
    "розыгрыш",      # покрывает розыгрыш/розыгрыша/розыгрыше
    "разыгрываем",   # покрывает разыгрываем/разыгрывается
    "giveaway",
    "конкурс",
    "выиграй",
    "победитель",
    "победители",
    "raffle",
    "sweepstake",
]

# Системные username, на которые НЕ подписываемся
USERNAME_BLACKLIST = {
    "telegram", "blog", "addstickers", "share", "joinchat",
    "c", "s", "telegra", "telegraph", "tg", "t"
}

# База данных
DB_PATH = os.getenv("DB_PATH", "../giveaways.db")
