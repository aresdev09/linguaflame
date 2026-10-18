"""Тесты подготовки БД при старте: миграции и банк вопросов."""

import sqlite3
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.bootstrap import (
    build_alembic_config,
    head_revision,
    load_question_bank,
    prepare_database,
    upgrade_database,
)
from bot.config import Settings
from bot.services.question_bank import BANK_PATH


def _sqlite_url(path: Path) -> str:
    return f"sqlite+aiosqlite:///{path.as_posix()}"


def _table_names(path: Path) -> set[str]:
    with sqlite3.connect(path) as connection:
        rows = connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        return {row[0] for row in rows}


def _alembic_revision(path: Path) -> str:
    with sqlite3.connect(path) as connection:
        return connection.execute("SELECT version_num FROM alembic_version").fetchone()[0]


async def test_upgrade_database_creates_schema(tmp_path: Path) -> None:
    database_url = _sqlite_url(tmp_path / "bot.db")

    await upgrade_database(database_url)

    tables = _table_names(tmp_path / "bot.db")
    assert {"users", "questions", "streaks", "activity_log", "level_tests"} <= tables
    assert _alembic_revision(tmp_path / "bot.db") == head_revision(
        build_alembic_config(database_url)
    )


async def test_upgrade_database_is_idempotent(tmp_path: Path) -> None:
    database_url = _sqlite_url(tmp_path / "bot.db")

    await upgrade_database(database_url)
    await upgrade_database(database_url)

    assert "users" in _table_names(tmp_path / "bot.db")


async def test_prepare_database_runs_migrations(tmp_path: Path) -> None:
    database_url = _sqlite_url(tmp_path / "bot.db")
    settings = Settings(bot_token="123:TEST", database_url=database_url, _env_file=None)

    await prepare_database(settings, bank=False)

    assert "users" in _table_names(tmp_path / "bot.db")


async def test_load_question_bank_is_idempotent(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    added, skipped = await load_question_bank(session_factory, BANK_PATH)
    assert added > 0
    assert skipped == 0

    again_added, again_skipped = await load_question_bank(session_factory, BANK_PATH)
    assert again_added == 0
    assert again_skipped == added
