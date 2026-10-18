"""Тесты серии дней и статистики.

Отдельное внимание — границе суток: часовой пояс Asia/Samarkand (UTC+5),
действия в 23:30 и 00:30 по местному времени.
"""

from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.models import ActivityLog, Streak
from bot.repositories import StreakRepo, UserRepo
from bot.services.streak import get_user_stats, register_activity

USER_ID = 777
SAMARKAND = ZoneInfo("Asia/Samarkand")


async def _create_user(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    timezone_name: str = "Asia/Samarkand",
) -> None:
    async with session_factory() as session:
        async with session.begin():
            await UserRepo(session).create(USER_ID, native_language="ru", timezone=timezone_name)


async def _register(
    session_factory: async_sessionmaker[AsyncSession],
    moment: datetime,
    kind: str = "quiz",
):
    async with session_factory() as session:
        async with session.begin():
            return await register_activity(session, USER_ID, kind, now=moment)


async def _streak(session_factory: async_sessionmaker[AsyncSession]) -> Streak | None:
    async with session_factory() as session:
        return await StreakRepo(session).get(USER_ID)


async def _kinds(session_factory: async_sessionmaker[AsyncSession]) -> list[str]:
    async with session_factory() as session:
        rows = await session.scalars(
            select(ActivityLog.kind).where(ActivityLog.user_id == USER_ID).order_by(ActivityLog.id)
        )
        return list(rows)


async def test_first_activity_starts_streak(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _create_user(session_factory)

    result = await _register(session_factory, datetime(2026, 10, 18, 9, 0, tzinfo=SAMARKAND))

    assert result.current_streak == 1
    assert result.best_streak == 1
    assert result.increased is True
    assert result.last_activity_date == date(2026, 10, 18)

    streak = await _streak(session_factory)
    assert streak is not None
    assert streak.current_streak == 1
    assert streak.best_streak == 1
    assert streak.last_activity_date == date(2026, 10, 18)
    assert await _kinds(session_factory) == ["quiz"]


async def test_yesterday_then_today_increases_by_one(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _create_user(session_factory)

    await _register(session_factory, datetime(2026, 10, 17, 12, 0, tzinfo=SAMARKAND))
    result = await _register(session_factory, datetime(2026, 10, 18, 12, 0, tzinfo=SAMARKAND))

    assert result.current_streak == 2
    assert result.best_streak == 2
    assert result.increased is True


async def test_skipped_day_resets_streak_but_keeps_best(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _create_user(session_factory)
    for day in (14, 15, 16):
        await _register(session_factory, datetime(2026, 10, day, 12, 0, tzinfo=SAMARKAND))
    assert (await _streak(session_factory)).current_streak == 3

    # 17 октября пропущено
    result = await _register(session_factory, datetime(2026, 10, 18, 12, 0, tzinfo=SAMARKAND))

    assert result.current_streak == 1
    assert result.best_streak == 3  # рекорд сохраняется
    assert result.increased is True


async def test_two_actions_same_day_grow_streak_only_once(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _create_user(session_factory)

    first = await _register(
        session_factory,
        datetime(2026, 10, 18, 9, 0, tzinfo=SAMARKAND),
        kind="quiz",
    )
    second = await _register(
        session_factory,
        datetime(2026, 10, 18, 21, 0, tzinfo=SAMARKAND),
        kind="vocabulary",
    )

    assert (first.current_streak, first.increased) == (1, True)
    assert (second.current_streak, second.increased) == (1, False)
    assert second.best_streak == 1
    # оба действия остаются в логе, серия при этом не растёт
    assert await _kinds(session_factory) == ["quiz", "vocabulary"]


async def test_midnight_boundary_in_samarkand_starts_new_day(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """23:30 и 00:30 по Самарканду — разные местные дни, хотя в UTC это один день."""
    await _create_user(session_factory)
    before_midnight = datetime(2026, 10, 17, 23, 30, tzinfo=SAMARKAND)
    after_midnight = datetime(2026, 10, 18, 0, 30, tzinfo=SAMARKAND)

    # сравнение календарных дат в UTC дало бы здесь один день и ошибку
    assert before_midnight.astimezone(UTC).date() == date(2026, 10, 17)
    assert after_midnight.astimezone(UTC).date() == date(2026, 10, 17)

    first = await _register(session_factory, before_midnight)
    second = await _register(session_factory, after_midnight)

    assert first.last_activity_date == date(2026, 10, 17)
    assert second.last_activity_date == date(2026, 10, 18)
    assert first.increased is True
    assert second.increased is True
    assert second.current_streak == 2


async def test_same_local_day_across_utc_midnight_grows_only_once(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """00:30 и 23:30 по Самарканду — один местный день, хотя в UTC это разные даты."""
    await _create_user(session_factory)
    after_local_midnight = datetime(2026, 10, 18, 0, 30, tzinfo=SAMARKAND)
    before_local_midnight = datetime(2026, 10, 18, 23, 30, tzinfo=SAMARKAND)

    assert after_local_midnight.astimezone(UTC).date() == date(2026, 10, 17)
    assert before_local_midnight.astimezone(UTC).date() == date(2026, 10, 18)

    first = await _register(session_factory, after_local_midnight)
    second = await _register(session_factory, before_local_midnight)

    assert first.current_streak == 1
    assert second.current_streak == 1
    assert second.increased is False


async def test_utc_user_counts_by_utc_days(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Для пользователя с UTC-поясом вчера и сегодня — это даты UTC."""
    await _create_user(session_factory, timezone_name="UTC")

    await _register(session_factory, datetime(2026, 10, 17, 23, 30, tzinfo=UTC))
    result = await _register(session_factory, datetime(2026, 10, 18, 0, 30, tzinfo=UTC))

    assert result.current_streak == 2
    assert result.last_activity_date == date(2026, 10, 18)


async def test_unknown_timezone_falls_back_to_utc(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _create_user(session_factory, timezone_name="Mars/Olympus")

    result = await _register(session_factory, datetime(2026, 10, 17, 23, 30, tzinfo=UTC))

    assert result.last_activity_date == date(2026, 10, 17)
    assert result.current_streak == 1


async def test_unknown_activity_kind_is_rejected(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _create_user(session_factory)

    with pytest.raises(ValueError):
        async with session_factory() as session:
            async with session.begin():
                await register_activity(session, USER_ID, "singing", now=datetime.now(UTC))


async def test_register_activity_requires_existing_user(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    with pytest.raises(ValueError):
        await _register(session_factory, datetime(2026, 10, 18, 12, 0, tzinfo=SAMARKAND))


async def test_stats_shows_current_best_and_week_actions(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _create_user(session_factory)
    # действие вне недельного окна и свежая серия из трёх дней
    await _register(session_factory, datetime(2026, 10, 8, 12, 0, tzinfo=SAMARKAND))
    for day in (16, 17, 18):
        await _register(session_factory, datetime(2026, 10, day, 12, 0, tzinfo=SAMARKAND))

    async with session_factory() as session:
        stats = await get_user_stats(
            session, USER_ID, now=datetime(2026, 10, 18, 20, 0, tzinfo=SAMARKAND)
        )

    assert stats.current_streak == 3
    assert stats.best_streak == 3
    assert stats.activities_week == 3  # 8 октября уже вне недели


async def test_stats_keep_streak_alive_if_last_action_was_yesterday(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _create_user(session_factory)
    await _register(session_factory, datetime(2026, 10, 17, 12, 0, tzinfo=SAMARKAND))

    async with session_factory() as session:
        stats = await get_user_stats(
            session, USER_ID, now=datetime(2026, 10, 18, 12, 0, tzinfo=SAMARKAND)
        )

    assert stats.current_streak == 1
    assert stats.best_streak == 1
    assert stats.activities_week == 1


async def test_stats_reset_stale_streak_to_zero(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _create_user(session_factory)
    await _register(session_factory, datetime(2026, 10, 10, 12, 0, tzinfo=SAMARKAND))

    async with session_factory() as session:
        stats = await get_user_stats(
            session, USER_ID, now=datetime(2026, 10, 18, 20, 0, tzinfo=SAMARKAND)
        )

    assert stats.current_streak == 0  # день пропущен
    assert stats.best_streak == 1
    assert stats.activities_week == 0


async def test_stats_without_activity_are_zero(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _create_user(session_factory)

    async with session_factory() as session:
        stats = await get_user_stats(
            session, USER_ID, now=datetime(2026, 10, 18, 20, 0, tzinfo=SAMARKAND)
        )

    assert (stats.current_streak, stats.best_streak, stats.activities_week) == (0, 0, 0)
