"""Тест команды /stats."""

import inspect
from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.locales import t
from bot.middlewares.user import UserMiddleware
from bot.repositories import ActivityRepo, StreakRepo, UserRepo
from bot.routers.stats import stats_command

USER_ID = 888
SAMARKAND = ZoneInfo("Asia/Samarkand")


class FakeTelegramUser:
    def __init__(self, user_id: int, first_name: str = "Аня") -> None:
        self.id = user_id
        self.first_name = first_name
        self.username = None


class FakeMessage:
    def __init__(self) -> None:
        self.from_user = FakeTelegramUser(USER_ID)
        self.answers: list[str] = []

    async def answer(self, text: str, **kwargs: Any) -> None:
        self.answers.append(text)


class FakeUpdate:
    """Апдейт в форме aiogram: middleware видит Update, хендлер — вложенное событие."""

    def __init__(self, event: Any, update_id: int = 1) -> None:
        self.event = event
        self.update_id = update_id


def _as_aiogram_caller(handler: Any) -> Any:
    """Как aiogram: в хендлер уходят только параметры из его сигнатуры."""

    async def caller(event: Any, data: dict[str, Any]) -> Any:
        params = inspect.signature(handler).parameters
        kwargs = {key: value for key, value in data.items() if key in params}
        return await handler(event, **kwargs)

    return caller


async def _dispatch(
    session_factory: async_sessionmaker[AsyncSession],
    message: FakeMessage,
) -> None:
    middleware = UserMiddleware()
    caller = _as_aiogram_caller(stats_command)

    async def on_update(update: Any, data: dict[str, Any]) -> Any:
        return await caller(message, data)

    async with session_factory() as session:
        async with session.begin():
            data = {"session": session, "event_from_user": message.from_user}
            await middleware(on_update, FakeUpdate(message), data)


async def test_stats_command_shows_streak_best_and_week(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    today_local = datetime.now(timezone.utc).astimezone(SAMARKAND).date()

    async with session_factory() as session:
        async with session.begin():
            await UserRepo(session).create(
                USER_ID, native_language="ru", timezone="Asia/Samarkand"
            )
            await StreakRepo(session).set_progress(
                USER_ID,
                current_streak=4,
                best_streak=7,
                last_activity_date=today_local,
            )
            await ActivityRepo(session).add(USER_ID, "quiz")
            await ActivityRepo(session).add(USER_ID, "vocabulary")

    message = FakeMessage()
    await _dispatch(session_factory, message)

    expected = "\n".join(
        [
            t("stats.title", "ru"),
            t("stats.current", "ru", days=4),
            t("stats.best", "ru", days=7),
            t("stats.week", "ru", count=2),
        ]
    )
    assert message.answers == [expected]


async def test_stats_command_shows_hint_without_streak(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        async with session.begin():
            await UserRepo(session).create(
                USER_ID, native_language="ru", timezone="Asia/Samarkand"
            )

    message = FakeMessage()
    await _dispatch(session_factory, message)

    assert message.answers[0].splitlines()[-1] == t("stats.hint", "ru")
    assert t("stats.current", "ru", days=0) in message.answers[0]
    assert t("stats.best", "ru", days=0) in message.answers[0]
