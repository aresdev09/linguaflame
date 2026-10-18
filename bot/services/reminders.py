"""Планирование напоминаний о занятиях.

Правила:
- утро 09:00 — только если сегодня активности ещё не было;
- вечер 20:00 — с текущей серией, тоже только без активности за день;
- 10:00 следующего дня после пропуска — «Где ты?» и потеря огонька;
- 3 и 7 дней без занятий — ещё одно мягкое напоминание;
- после 7 дней молчания рассылка останавливается до новой активности;
- не больше 2 сообщений в сутки, повторный запуск в тот же час не даёт дубля.

Здесь нет aiogram: решение о сообщении, тексты и обновление полей серии.
Отправку и обработку ошибок Telegram делает `bot.scheduler`.
"""

import logging
import zlib
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from bot.locales import t
from bot.models import Streak, User
from bot.repositories import StreakRepo
from bot.services.ai_schemas import Word
from bot.services.timezones import as_utc, resolve_timezone
from bot.services.vocabulary import format_transcription

logger = logging.getLogger(__name__)

MORNING_HOUR = 9
EVENING_HOUR = 20
MISSED_HOUR = 10

# Не больше двух сообщений от планировщика в сутки на пользователя.
MAX_PER_DAY = 2

# После стольких дней без занятий рассылка прекращается (8-й день — тишина).
MAX_SILENT_DAYS = 7

# Дни с последней активности, когда приходит «Где ты?»/мягкое напоминание:
# 2 — следующий день после пропуска, 3 и 7 — по таблице напоминаний.
MISSED_DAYS: tuple[int, ...] = (2, 3, 7)

# Сколько вариантов текста есть у каждого вида напоминания.
VARIANTS: dict[str, int] = {
    "morning": 3,
    "evening": 3,
    "evening_cold": 2,
    "missed": 3,
    "missed_long": 2,
}

# Быстрый старт из напоминания: небольшой набор слов.
QUICK_START_WORDS = 5


@dataclass(frozen=True)
class Reminder:
    """Что именно отправить пользователю и как обновить его серию."""

    slot: str
    days: int = 0
    reset_streak: bool = False


def _local_date(moment: datetime, user: User) -> date:
    return moment.astimezone(resolve_timezone(user.timezone, user_id=user.id)).date()


def _silent_days(today: date, user: User, streak: Streak | None) -> int:
    """Сколько дней прошло с последней активности (или регистрации)."""
    last = streak.last_activity_date if streak else None
    if last is not None:
        return (today - last).days
    created = as_utc(user.created_at).astimezone(resolve_timezone(user.timezone, user_id=user.id))
    return (today - created.date()).days


def _alive_streak(streak: Streak | None, today: date) -> int:
    """Текущая серия, которая ещё жива: сегодня или вчера было действие."""
    if streak is None or streak.last_activity_date is None:
        return 0
    if streak.last_activity_date in (today, today - timedelta(days=1)):
        return streak.current_streak
    return 0


def plan_reminder(
    user: User,
    streak: Streak | None,
    now: datetime,
) -> Reminder | None:
    """Решает, какое напоминание нужно пользователю в этот момент."""
    if not user.is_active:
        return None

    moment = as_utc(now)
    timezone_info = resolve_timezone(user.timezone, user_id=user.id)
    local = moment.astimezone(timezone_info)
    today = local.date()
    hour = local.hour
    last_activity = streak.last_activity_date if streak else None
    activity_today = last_activity == today

    if _silent_days(today, user, streak) > MAX_SILENT_DAYS:
        return None

    if hour == MORNING_HOUR:
        if activity_today:
            return None
        return Reminder(slot="morning")

    if hour == EVENING_HOUR:
        if activity_today:
            return None
        alive = _alive_streak(streak, today)
        if alive > 0:
            return Reminder(slot="evening", days=alive)
        return Reminder(slot="evening_cold")

    if hour != MISSED_HOUR or last_activity is None:
        return None

    silent = (today - last_activity).days
    if silent in MISSED_DAYS:
        lost = streak.current_streak if streak else 0
        if silent == 2:
            return Reminder(slot="missed", days=lost, reset_streak=True)
        return Reminder(slot="missed_long", days=silent)

    return None


def reminder_text(reminder: Reminder, user: User, now: datetime) -> str:
    """Текст напоминания на языке пользователя.

    Вариант выбирается детерминированно по пользователю и дню, поэтому
    повторный запуск в тот же час пришлёт тот же текст (или не пришлёт его).
    """
    count = VARIANTS[reminder.slot]
    day = _local_date(as_utc(now), user)
    seed = f"{user.id}:{day.isoformat()}:{reminder.slot}".encode()
    index = 1 + zlib.crc32(seed) % count
    return t(f"reminder.{reminder.slot}.{index}", user.native_language, days=reminder.days)


def reminder_allowed(
    user: User,
    streak: Streak | None,
    now: datetime,
) -> bool:
    """Проверяет лимит двух сообщений в сутки и повторный запуск в тот час."""
    if not user.is_active:
        return False

    moment = as_utc(now)
    timezone_info = resolve_timezone(user.timezone, user_id=user.id)
    local = moment.astimezone(timezone_info)

    if streak is not None and streak.reminders_date == local.date():
        if streak.reminders_count >= MAX_PER_DAY:
            return False

    if streak is not None and streak.last_reminder_at is not None:
        last_local = as_utc(streak.last_reminder_at).astimezone(timezone_info)
        if last_local.date() == local.date() and last_local.hour == local.hour:
            return False

    return True


async def mark_reminder_sent(
    session: AsyncSession,
    user: User,
    reminder: Reminder,
    now: datetime,
) -> None:
    """Записывает отправку: время, счётчик за день и потерю серии."""
    moment = as_utc(now)
    repo = StreakRepo(session)
    streak = await repo.get_or_create(user.id)
    today = _local_date(moment, user)

    if streak.reminders_date != today:
        streak.reminders_date = today
        streak.reminders_count = 0

    streak.reminders_count += 1
    streak.last_reminder_at = moment
    if reminder.reset_streak and streak.current_streak > 0:
        # Огонёк потерян; рекорд best_streak не трогаем.
        streak.current_streak = 0
    await session.flush()

    logger.info(
        "Напоминание %s: пользователь %s, сообщений за день %d",
        reminder.slot,
        user.id,
        streak.reminders_count,
    )


def format_quick_words(words: list[Word], lang: str) -> str:
    """Короткий список слов для кнопки быстрого старта."""
    lines = [t("reminder.quick_title", lang, count=len(words)), ""]
    lines.extend(
        t(
            "vocabulary.item",
            lang,
            index=index,
            word=word.word,
            transcription=format_transcription(word.transcription),
            translation=word.translation,
        )
        for index, word in enumerate(words, start=1)
    )
    return "\n".join(lines)
