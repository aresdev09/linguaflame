"""Серия дней («огонёк») и статистика прогресса.

Правила:
- серия считается по календарным дням в часовом поясе пользователя;
- первое действие дня даёт +1, действия в тот же день серию не растят;
- пропуск дня сбрасывает серию до 1 при следующем действии;
- `best_streak` хранит рекорд и никогда не уменьшается.
"""

import logging
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from bot.repositories import ActivityRepo, StreakRepo, UserRepo
from bot.services.timezones import as_utc, resolve_timezone

logger = logging.getLogger(__name__)

ActivityKind = Literal["quiz", "grammar", "vocabulary", "essay", "chat", "level_test"]

ACTIVITY_KINDS: frozenset[str] = frozenset(
    ("quiz", "grammar", "vocabulary", "essay", "chat", "level_test")
)

WEEK_DAYS = 7


@dataclass(frozen=True)
class ActivityResult:
    """Что стало с серией после учебного действия."""

    current_streak: int
    best_streak: int
    increased: bool
    last_activity_date: date


@dataclass(frozen=True)
class UserStats:
    """Статистика прогресса пользователя."""

    current_streak: int
    best_streak: int
    activities_week: int


async def register_activity(
    session: AsyncSession,
    user_id: int,
    kind: ActivityKind,
    *,
    now: datetime | None = None,
) -> ActivityResult:
    """Записывает учебное действие и обновляет серию дней пользователя.

    Вызывается из любого учебного сценария (квиз, урок, слова, эссе, тест,
    свободный чат). `now` нужен тестам, в бою берётся текущий момент.
    """
    if kind not in ACTIVITY_KINDS:
        raise ValueError(f"Неизвестный вид активности: {kind!r}")

    moment = as_utc(now)
    user = await UserRepo(session).get(user_id)
    if user is None:
        raise ValueError(f"Пользователь {user_id} не найден")

    timezone_info = resolve_timezone(user.timezone, user_id=user_id)
    today = moment.astimezone(timezone_info).date()

    streak_repo = StreakRepo(session)
    streak = await streak_repo.get_or_create(user_id)
    last = streak.last_activity_date
    current = streak.current_streak
    best = streak.best_streak

    if last is not None and last >= today:
        # Сегодня уже занимался: серия не растёт, дату не откатываем.
        increased = False
    else:
        increased = True
        current = current + 1 if last == today - timedelta(days=1) else 1
        best = max(best, current)
        last = today

    await streak_repo.set_progress(
        user_id,
        current_streak=current,
        best_streak=best,
        last_activity_date=last,
    )
    await ActivityRepo(session).add(user_id, kind, created_at=moment)

    logger.info(
        "Активность %s: пользователь %s, серия %d (рекорд %d), рост: %s",
        kind,
        user_id,
        current,
        best,
        increased,
    )
    return ActivityResult(
        current_streak=current,
        best_streak=best,
        increased=increased,
        last_activity_date=last,
    )


async def get_user_stats(
    session: AsyncSession,
    user_id: int,
    *,
    now: datetime | None = None,
) -> UserStats:
    """Текущая серия, рекорд и число действий за последние 7 календарных дней.

    Серия «жива», если последнее действие было сегодня или вчера; иначе 0
    (в БД она обновится до 1 при следующем действии).
    """
    moment = as_utc(now)
    user = await UserRepo(session).get(user_id)
    if user is None:
        raise ValueError(f"Пользователь {user_id} не найден")

    timezone_info = resolve_timezone(user.timezone, user_id=user_id)
    local_today = moment.astimezone(timezone_info).date()

    streak = await StreakRepo(session).get(user_id)
    current = streak.current_streak if streak else 0
    best = streak.best_streak if streak else 0
    last = streak.last_activity_date if streak else None

    if last is None or last < local_today - timedelta(days=1):
        current = 0

    week_start_local = datetime.combine(
        local_today - timedelta(days=WEEK_DAYS - 1),
        time.min,
        tzinfo=timezone_info,
    )
    activities = await ActivityRepo(session).count_since(
        user_id, week_start_local.astimezone(timezone.utc)
    )

    return UserStats(
        current_streak=current,
        best_streak=best,
        activities_week=activities,
    )
