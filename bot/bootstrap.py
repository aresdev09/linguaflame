"""Подготовка БД при старте: миграции Alembic и банк вопросов.

Панели хостинга обычно запускают только `python main.py`, поэтому схема
не может оставаться ручным шагом: без неё первый же апдейт падает с
`no such table: users`. Обе операции идемпотентны, их безопасно выполнять
на каждом запуске.
"""

import asyncio
import logging
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.config import Settings
from bot.database import get_session_factory
from bot.services.question_bank import (
    BANK_FILES,
    DEFAULT_BANK_LANGUAGE,
    insert_bank,
    load_bank,
    validate_bank,
)

logger = logging.getLogger(__name__)

# Корень проекта: рядом лежат alembic.ini и migrations/.
PROJECT_ROOT = Path(__file__).resolve().parents[1]


class DatabaseSetupError(RuntimeError):
    """Понятная ошибка подготовки БД, показывается пользователю при запуске."""


def build_alembic_config(database_url: str) -> Config:
    """Конфиг Alembic с адресом БД и без перезаписи логирования приложения."""
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(PROJECT_ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    # env.py читает эти значения из attributes: адрес БД важнее переменных
    # окружения, а fileConfig() не должен глушить уже настроенные логгеры.
    config.attributes["database_url"] = database_url
    config.attributes["skip_logging_config"] = True
    return config


def head_revision(config: Config) -> str:
    """Последняя ревизия из каталога миграций."""
    head = ScriptDirectory.from_config(config).get_current_head()
    if head is None:
        raise DatabaseSetupError("В migrations/versions нет ни одной миграции")
    return head


async def upgrade_database(database_url: str) -> None:
    """Применяет все миграции (`alembic upgrade head`).

    Alembic в env.py запускает собственный `asyncio.run`, поэтому работу
    выносим в отдельный поток: внутри работающего event loop это иначе упадёт.
    """
    config = build_alembic_config(database_url)
    revision = head_revision(config)
    logger.info("Применяю миграции БД до %s", revision)
    try:
        await asyncio.to_thread(command.upgrade, config, "head")
    except DatabaseSetupError:
        raise
    except Exception as exc:
        raise DatabaseSetupError(
            "Не удалось применить миграции БД. Проверьте DATABASE_URL "
            f"и доступность базы данных.\n{exc}"
        ) from exc
    logger.info("Схема БД готова (revision %s)", revision)


async def load_question_bank(
    session_factory: async_sessionmaker[AsyncSession] | None = None,
    path: Path | None = None,
    language: str | None = None,
) -> tuple[int, int]:
    """Догружает банк вопросов уровня в `questions` (без дублей).

    Без аргументов загружает все известные банки (`BANK_FILES`). `path` и
    `language` позволяют загрузить один конкретный файл: путь к нему и язык
    пояснений, который будет сохранён в вопросах.
    Возвращает (добавлено, уже было) — суммарно по всем банкам.
    """
    factory = session_factory or get_session_factory()
    if path is not None:
        banks = [(language or DEFAULT_BANK_LANGUAGE, path)]
    else:
        banks = list(BANK_FILES.items())

    total_added = 0
    total_skipped = 0
    async with factory() as session:
        async with session.begin():
            for bank_language, bank_path in banks:
                questions = load_bank(bank_path)
                validate_bank(questions)
                stats = await insert_bank(session, questions, language=bank_language)
                total_added += stats.added
                total_skipped += stats.skipped
    return total_added, total_skipped


async def prepare_database(settings: Settings, *, bank: bool = True) -> None:
    """Готовит БД к работе бота: миграции и (по желанию) банк вопросов."""
    await upgrade_database(settings.database_url)

    if not bank:
        return
    try:
        added, skipped = await load_question_bank()
    except Exception:
        # Без банка /quiz и /level_detector переходят на генерацию через ИИ,
        # поэтому старт бота из-за него не останавливаем.
        logger.exception(
            "Не удалось загрузить банк вопросов; вопросы будут генерироваться через ИИ"
        )
        return
    logger.info("Банк вопросов готов: добавлено %d, уже было %d", added, skipped)
