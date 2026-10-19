"""Тесты настройки SQLite и повторов записи при блокировке.

Проверяем то, из-за чего на хостинге падало `database is locked`:
WAL и busy timeout включаются самим движком, а короткие транзакции
повторяются, если файл всё-таки оказался занят.
"""

from pathlib import Path

import pytest
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.database import build_engine, sqlite_connect_args, transaction_with_retry


def _locked_error() -> OperationalError:
    """Ошибка SQLite, когда запись не получила блокировку."""
    return OperationalError(
        "UPDATE ai_usage SET requests=? WHERE user_id = ?",
        {},
        Exception("database is locked"),
    )


def test_sqlite_connect_args_wait_for_lock() -> None:
    assert sqlite_connect_args("sqlite+aiosqlite:///./linguflame.db") == {"timeout": 30}


def test_postgres_keeps_its_own_connect_args() -> None:
    assert sqlite_connect_args("postgresql+asyncpg://user:pass@db:5432/linguflame") == {}


async def test_sqlite_engine_enables_wal_and_busy_timeout(tmp_path: Path) -> None:
    engine = build_engine(f"sqlite+aiosqlite:///{(tmp_path / 'tuned.db').as_posix()}")
    try:
        async with engine.connect() as connection:
            journal = await connection.exec_driver_sql("PRAGMA journal_mode")
            timeout = await connection.exec_driver_sql("PRAGMA busy_timeout")
            synchronous = await connection.exec_driver_sql("PRAGMA synchronous")

        assert journal.scalar() == "wal"
        assert timeout.scalar() == 30000
        assert synchronous.scalar() == 1  # NORMAL — как в SQLAlchemy-рецепте для WAL
    finally:
        await engine.dispose()


async def test_transaction_with_retry_repeats_locked_write(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    attempts = 0

    async def action(session: AsyncSession) -> str:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise _locked_error()
        return "ok"

    assert await transaction_with_retry(session_factory, action) == "ok"
    assert attempts == 2


async def test_transaction_with_retry_reraises_other_errors(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async def action(session: AsyncSession) -> str:
        raise OperationalError("SELECT 1", {}, Exception("no such table: nope"))

    with pytest.raises(OperationalError):
        await transaction_with_retry(session_factory, action)
