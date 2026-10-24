"""Тесты скрипта поддержки `scripts.set_user_level` (задача: сброс уровня)."""

from datetime import datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.repositories import UserRepo
from scripts import set_user_level


@pytest.fixture
def use_test_db(
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> async_sessionmaker[AsyncSession]:
    """Подменяет фабрику сессий скрипта на тестовую БД в памяти."""
    monkeypatch.setattr(set_user_level, "get_session_factory", lambda: session_factory)
    return session_factory


async def test_script_sets_level_and_date(
    use_test_db: async_sessionmaker[AsyncSession],
) -> None:
    async with use_test_db() as session:
        async with session.begin():
            await UserRepo(session).get_or_create(777)

    code = await set_user_level.main(777, "A2", False)

    assert code == 0
    async with use_test_db() as session:
        user = await UserRepo(session).get(777)
        assert user is not None
        assert user.level == "A2"
        assert isinstance(user.level_tested_at, datetime)


async def test_script_resets_level(
    use_test_db: async_sessionmaker[AsyncSession],
) -> None:
    async with use_test_db() as session:
        async with session.begin():
            repo = UserRepo(session)
            await repo.get_or_create(777)
            await repo.set_level(777, "C2", datetime.now())

    code = await set_user_level.main(777, None, True)

    assert code == 0
    async with use_test_db() as session:
        user = await UserRepo(session).get(777)
        assert user is not None
        assert user.level is None
        assert user.level_tested_at is None


async def test_script_reports_unknown_user(
    use_test_db: async_sessionmaker[AsyncSession],
) -> None:
    code = await set_user_level.main(123, "A2", False)

    assert code == 1
