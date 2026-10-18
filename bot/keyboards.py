"""Клавиатуры бота.

Подписи кнопок берутся из локализации, `callback_data` — технические.
"""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.locales import t

LANGUAGE_CALLBACK_PREFIX = "lang:"
TIMEZONE_CALLBACK_PREFIX = "tz:"

# Часовые пояса: (IANA-идентификатор, ключ подписи в локализации)
TIMEZONES: tuple[tuple[str, str], ...] = (
    ("UTC", "timezone.utc"),
    ("Europe/Moscow", "timezone.moscow"),
    ("Asia/Tashkent", "timezone.tashkent"),
    ("Asia/Samarkand", "timezone.samarkand"),
    ("Europe/Berlin", "timezone.berlin"),
    ("Europe/London", "timezone.london"),
    ("America/New_York", "timezone.new_york"),
)


def language_kb(lang: str) -> InlineKeyboardMarkup:
    """Кнопки выбора родного языка."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=t("language.ru", lang),
                    callback_data=f"{LANGUAGE_CALLBACK_PREFIX}ru",
                ),
                InlineKeyboardButton(
                    text=t("language.en", lang),
                    callback_data=f"{LANGUAGE_CALLBACK_PREFIX}en",
                ),
            ]
        ]
    )


def timezone_kb(lang: str) -> InlineKeyboardMarkup:
    """Кнопки выбора часового пояса, по две в ряд."""
    buttons = [
        InlineKeyboardButton(
            text=t(key, lang),
            callback_data=f"{TIMEZONE_CALLBACK_PREFIX}{timezone}",
        )
        for timezone, key in TIMEZONES
    ]
    rows = [buttons[i : i + 2] for i in range(0, len(buttons), 2)]
    return InlineKeyboardMarkup(inline_keyboard=rows)