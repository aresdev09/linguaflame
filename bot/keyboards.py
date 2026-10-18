"""Клавиатуры бота.

Подписи кнопок берутся из локализации, `callback_data` — технические.
"""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.locales import t

LANGUAGE_CALLBACK_PREFIX = "lang:"
TIMEZONE_CALLBACK_PREFIX = "tz:"
QUIZ_CALLBACK_PREFIX = "quiz:"
QUIZ_FINISH_CALLBACK = f"{QUIZ_CALLBACK_PREFIX}finish"
LEVEL_CALLBACK_PREFIX = "level:"
LEVEL_START_CALLBACK = f"{LEVEL_CALLBACK_PREFIX}start"
LEVEL_CANCEL_CALLBACK = f"{LEVEL_CALLBACK_PREFIX}cancel"
GRAMMAR_CALLBACK_PREFIX = "grammar:"
GRAMMAR_NEXT_CALLBACK_PREFIX = f"{GRAMMAR_CALLBACK_PREFIX}next:"
GRAMMAR_CONTINUE_CALLBACK = f"{GRAMMAR_CALLBACK_PREFIX}continue"
GRAMMAR_RESTART_CALLBACK = f"{GRAMMAR_CALLBACK_PREFIX}restart"
GRAMMAR_TEST_CALLBACK_PREFIX = f"{GRAMMAR_CALLBACK_PREFIX}test:"
REMINDER_QUICK_CALLBACK = "reminder:quick"

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


def quiz_options_kb(
    question_id: int,
    options: dict[str, str],
    lang: str,
) -> InlineKeyboardMarkup:
    """Варианты ответа A, B, C и кнопка завершения квиза."""
    rows = [
        [
            InlineKeyboardButton(
                text=f"{option}) {text}",
                callback_data=f"{QUIZ_CALLBACK_PREFIX}{question_id}:{option}",
            )
        ]
        for option, text in sorted(options.items())
    ]
    rows.append(
        [
            InlineKeyboardButton(
                text=t("quiz.finish_button", lang),
                callback_data=QUIZ_FINISH_CALLBACK,
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def level_test_options_kb(
    question_id: int,
    options: dict[str, str],
) -> InlineKeyboardMarkup:
    """Варианты ответа теста уровня: без кнопки завершения."""
    rows = [
        [
            InlineKeyboardButton(
                text=f"{option}) {text}",
                callback_data=f"{LEVEL_CALLBACK_PREFIX}{question_id}:{option}",
            )
        ]
        for option, text in sorted(options.items())
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def level_retake_kb(lang: str) -> InlineKeyboardMarkup:
    """Кнопки подтверждения повторной сдачи теста."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=t("level.start_button", lang),
                    callback_data=LEVEL_START_CALLBACK,
                ),
                InlineKeyboardButton(
                    text=t("common.cancel", lang),
                    callback_data=LEVEL_CANCEL_CALLBACK,
                ),
            ]
        ]
    )


def grammar_next_kb(step_index: int, lang: str, *, resume: bool = False) -> InlineKeyboardMarkup:
    """Кнопка «Дальше» для шагов explanation и example."""
    key = "grammar.continue_button" if resume else "grammar.next_button"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=t(key, lang),
                    callback_data=f"{GRAMMAR_NEXT_CALLBACK_PREFIX}{step_index}",
                )
            ]
        ]
    )


def grammar_resume_kb(lang: str) -> InlineKeyboardMarkup:
    """Кнопки незавершённого урока: продолжить или начать заново."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=t("grammar.continue_button_short", lang),
                    callback_data=GRAMMAR_CONTINUE_CALLBACK,
                ),
                InlineKeyboardButton(
                    text=t("grammar.restart_button", lang),
                    callback_data=GRAMMAR_RESTART_CALLBACK,
                ),
            ]
        ]
    )


def grammar_test_kb(question_index: int, options: dict[str, str]) -> InlineKeyboardMarkup:
    """Варианты ответа A, B, C для мини-теста в конце урока."""
    rows = [
        [
            InlineKeyboardButton(
                text=f"{option}) {text}",
                callback_data=f"{GRAMMAR_TEST_CALLBACK_PREFIX}{question_index}:{option}",
            )
        ]
        for option, text in sorted(options.items())
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def reminder_quick_kb(lang: str) -> InlineKeyboardMarkup:
    """Кнопка быстрого старта под напоминанием."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=t("reminder.button", lang),
                    callback_data=REMINDER_QUICK_CALLBACK,
                )
            ]
        ]
    )


def empty_kb() -> InlineKeyboardMarkup:
    """Пустая клавиатура: убирает кнопки у сообщения."""
    return InlineKeyboardMarkup(inline_keyboard=[])