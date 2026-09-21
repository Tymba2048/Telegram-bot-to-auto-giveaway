import re
from datetime import datetime, date
from typing import List, Tuple


def find_giveaway_dates(text: str) -> List[Tuple[datetime, str]]:
    """
    Ищет в тексте даты в форматах:
      - dd.mm.yy
      - dd.mm.yyyy
      - dd.mm          (год отсутствует)
      - dd месяц yyyy
      - dd месяц       (год отсутствует)

    Возвращает список (parsed_datetime, исходная_строка_даты).
    Если год не указан — используется текущий год.
    """

    MONTHS_RU = {
        'января': 1,  'февраля': 2,  'марта': 3,    'апреля': 4,  'мая': 5,
        'июня': 6,    'июля': 7,    'августа': 8,  'сентября': 9,
        'октября': 10,'ноября': 11, 'декабря': 12
    }

    patterns = [
        # 1) dd.mm.yy или dd.mm.yyyy (год указан)
        r'(?P<day>\d{1,2})\.(?P<month>\d{1,2})\.(?P<year>\d{2,4})',

        # 2) dd.mm (год не указан)
        r'(?P<day_mm>\d{1,2})\.(?P<month_mm>\d{1,2})',

        # 3) dd месяц yyyy
        r'(?P<day_rus>\d{1,2})\s+'
        r'(?P<month_ru>января|февраля|марта|апреля|мая|июня|'
        r'июля|августа|сентября|октября|ноября|декабря)\s+'
        r'(?P<year_ru>\d{4})',

        # 4) dd месяц (год не указан)
        r'(?P<day_ru_no_year>\d{1,2})\s+'
        r'(?P<month_ru_no_year>января|февраля|марта|апреля|мая|июня|'
        r'июля|августа|сентября|октября|ноября|декабря)'
    ]

    results: List[Tuple[datetime, str]] = []
    current_year = date.today().year

    for pattern in patterns:
        for m in re.finditer(pattern, text, flags=re.IGNORECASE):
            gd = m.groupdict()

            try:
                # Вариант 1: dd.mm.yy или dd.mm.yyyy (год есть)
                if gd.get('year') is not None:
                    day = int(gd['day'])
                    month = int(gd['month'])
                    year = int(gd['year'])
                    # Двузначный год → 20xx (при необходимости можете изменить логику)
                    if year < 100:
                        year = 2000 + year

                # Вариант 2: dd.mm (год отсутствует)
                elif gd.get('day_mm') is not None:
                    day = int(gd['day_mm'])
                    month = int(gd['month_mm'])
                    year = current_year

                # Вариант 3: dd месяц yyyy
                elif gd.get('year_ru') is not None:
                    day = int(gd['day_rus'])
                    month = MONTHS_RU[gd['month_ru'].lower()]
                    year = int(gd['year_ru'])

                # Вариант 4: dd месяц (год отсутствует)
                elif gd.get('day_ru_no_year') is not None:
                    day = int(gd['day_ru_no_year'])
                    month = MONTHS_RU[gd['month_ru_no_year'].lower()]
                    year = current_year

                else:
                    continue

                parsed = datetime(year, month, day)
                results.append((parsed, m.group(0)))
            except (ValueError, KeyError):
                # Невалидная дата — пропускаем
                continue

    return results