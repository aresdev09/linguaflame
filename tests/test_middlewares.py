"""Тесты middleware."""

from types import SimpleNamespace
from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.locales import t
from bot.middlewares.db import DbSessionMiddleware
from bot.middlewares.errors import ErrorMiddleware
from bot.middlewares.throttle import ThrottleMiddleware
from bot.middlewares.user import UserMiddleware
from bot.models import User
from bot.repositories import UserRepo


class FakeTelegramUser:
    """Минимальный аналог telegram.User для middleware."""

    def __init__(self, user_id: int, username: str | None = None) -> None:
        self.id = user_id
        self.username = username
        self.first_name = "Test"


class FakeMessage:
    """Сообщение, которое только запоминает ответы."""

    def __init__(self, user_id: int = 1) -> None:
        self.from_user = FakeTelegramUser(user_id)
        self.answers: list[str] = []

    async def answer(self, text: str, **kwargs: Any) -> None:
        self.answers.append(text)


async def test_user_middleware_creates_user_once(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    middleware = UserMiddleware()
    event = SimpleNamespace(from_user=FakeTelegramUser(777, username="ann"))

    async def handler(event: Any, data: dict[str, Any]) -> bool:
        return data["is_new_user"]

    async with session_factory() as session:
        async with session.begin():
            assert await middleware(handler, event, {"session": session}) is True
        async with session.begin():
            assert await middleware(handler, event, {"session": session}) is False

        user = await UserRepo(session).get(777)
        assert user is not None
        assert user.username == "ann"
        assert user.native_language == "en"
        assert user.timezone == "UTC"
        assert await session.scalar(select(func.count()).select_from(User)) == 1


async def test_user_middleware_survives_creation_race(
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Параллельный апдейт уже создал пользователя: middleware не падает."""
    middleware = UserMiddleware()
    event = SimpleNamespace(from_user=FakeTelegramUser(888, username="ann"))

    async def handler(event: Any, data: dict[str, Any]) -> bool:
        return data["is_new_user"]

    # Пользователя уже создал параллельный апдейт в своей транзакции.
    async with session_factory() as session:
        async with session.begin():
            await UserRepo(session).create(888, username="ann")

    original_get = UserRepo.get
    misses = 0

    async def get_miss_once(self: UserRepo, user_id: int) -> User | None:
        nonlocal misses
        misses += 1
        if misses == 1:
            return None
        return await original_get(self, user_id)

    monkeypatch.setattr(UserRepo, "get", get_miss_once)

    async with session_factory() as session:
        async with session.begin():
            assert await middleware(handler, event, {"session": session}) is False

    async with session_factory() as session:
        assert await session.scalar(
            select(func.count()).select_from(User)
        ) == 1
        assert await session.scalar(select(User.username)) == "ann"


async def test_db_session_middleware_commits_on_success(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    middleware = DbSessionMiddleware(session_factory)

    async def handler(event: Any, data: dict[str, Any]) -> str:
        await UserRepo(data["session"]).create(5)
        return "ok"

    assert await middleware(handler, SimpleNamespace(), {}) == "ok"

    async with session_factory() as session:
        assert await UserRepo(session).get(5) is not None


async def test_db_session_middleware_rolls_back_on_error(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    middleware = DbSessionMiddleware(session_factory)

    async def handler(event: Any, data: dict[str, Any]) -> None:
        await UserRepo(data["session"]).create(6)
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        await middleware(handler, SimpleNamespace(), {})

    async with session_factory() as session:
        assert await UserRepo(session).get(6) is None


async def test_throttle_drops_updates_faster_than_one_per_second() -> None:
    now = 100.0
    middleware = ThrottleMiddleware(rate_limit=1.0, monotonic=lambda: now)
    calls = 0

    async def handler(event: Any, data: dict[str, Any]) -> str:
        nonlocal calls
        calls += 1
        return "ok"

    event = SimpleNamespace(from_user=FakeTelegramUser(10))
    data = {"user": SimpleNamespace(id=10)}

    assert await middleware(handler, event, data) == "ok"

    now = 100.5
    assert await middleware(handler, event, data) is None
    assert calls == 1

    now = 101.2
    assert await middleware(handler, event, data) == "ok"
    assert calls == 2


async def test_throttle_counts_every_user_separately() -> None:
    middleware = ThrottleMiddleware(rate_limit=1.0, monotonic=lambda: 50.0)

    async def handler(event: Any, data: dict[str, Any]) -> str:
        return "ok"

    first = {"user": SimpleNamespace(id=1)}
    second = {"user": SimpleNamespace(id=2)}

    assert await middleware(handler, SimpleNamespace(), first) == "ok"
    assert await middleware(handler, SimpleNamespace(), first) is None
    assert await middleware(handler, SimpleNamespace(), second) == "ok"


async def test_error_middleware_answers_user_in_their_language() -> None:
    middleware = ErrorMiddleware()
    event = FakeMessage()

    async def handler(event: Any, data: dict[str, Any]) -> None:
        raise RuntimeError("boom")

    result = await middleware(handler, event, {"user": SimpleNamespace(native_language="en")})

    assert result is None
    assert event.answers == [t("common.error", "en")]


async def test_error_middleware_works_without_user() -> None:
    middleware = ErrorMiddleware()
    event = FakeMessage()

    async def handler(event: Any, data: dict[str, Any]) -> None:
        raise RuntimeError("boom")

    await middleware(handler, event, {})

    assert event.answers == [t("common.error", None)]


async def test_error_middleware_passes_successful_result_through() -> None:
    middleware = ErrorMiddleware()

    async def handler(event: Any, data: dict[str, Any]) -> str:
        return "ok"

    assert await middleware(handler, FakeMessage(), {}) == "ok"


async def test_user_middleware_reads_user_from_event_from_user(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """На dp.update в event лежит Update без from_user, пользователь — в data."""
    middleware = UserMiddleware()
    update = SimpleNamespace(update_id=7)
    telegram_user = FakeTelegramUser(4242, username="kate")
    seen: dict[str, Any] = {}

    async def handler(event: Any, data: dict[str, Any]) -> int:
        seen.update(data)
        return data["user"].id

    async with session_factory() as session:
        async with session.begin():
            result = await middleware(
                handler,
                update,
                {"session": session, "event_from_user": telegram_user},
            )

    assert result == 4242
    assert seen["is_new_user"] is True


async def test_user_middleware_skips_updates_without_telegram_user(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Пост в канале: у апдейта нет пользователя, хендлер всё равно вызывается."""
    middleware = UserMiddleware()
    update = SimpleNamespace(update_id=8)

    async def handler(event: Any, data: dict[str, Any]) -> Any:
        return data.get("user")

    async with session_factory() as session:
        async with session.begin():
            assert await middleware(handler, update, {"session": session}) is None


async def test_throttle_works_without_user_in_data() -> None:
    middleware = ThrottleMiddleware(rate_limit=1.0, monotonic=lambda: 5.0)
    telegram_user = FakeTelegramUser(3)

    async def handler(event: Any, data: dict[str, Any]) -> str:
        return "ok"

    update = SimpleNamespace(update_id=9)
    data = {"event_from_user": telegram_user}

    assert await middleware(handler, update, data) == "ok"
    assert await middleware(handler, update, data) is None
