"""Загрузка банка вопросов уровня в таблицу `questions`.

Идемпотентно: повторный запуск не создаёт дубли.
Запуск из корня проекта:
    python -m scripts.load_level_questions
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bot.database import get_session_factory
from bot.logging_setup import setup_logging
from bot.services.question_bank import (
    BANK_PATH,
    insert_bank,
    load_bank,
    validate_bank,
)

logger = logging.getLogger(__name__)


async def main(path: Path) -> None:
    """Читает банк, проверяет его и загружает вопросы в БД."""
    questions = load_bank(path)
    counts = validate_bank(questions)
    print(f"В банке {len(questions)} вопросов:")
    for level in ("A1", "A2", "B1", "B2", "C1", "C2"):
        print(f"  {level}: {counts.for_level(level)}")

    session_factory = get_session_factory()
    async with session_factory() as session:
        async with session.begin():
            stats = await insert_bank(session, questions)
    print(f"Добавлено: {stats.added}, уже было: {stats.skipped}")


if __name__ == "__main__":
    setup_logging()
    parser = argparse.ArgumentParser(description="Загрузить банк вопросов уровня в БД")
    parser.add_argument(
        "--path",
        type=Path,
        default=BANK_PATH,
        help="путь к JSON-файлу банка",
    )
    arguments = parser.parse_args()
    asyncio.run(main(arguments.path))
