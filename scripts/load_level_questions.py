"""Загрузка банков вопросов уровня в таблицу `questions`.

Идемпотентно: повторный запуск не создаёт дубли. По умолчанию загружает все
известные банки (`BANK_FILES`), `--language` — только один из них.
Запуск из корня проекта:
    python -m scripts.load_level_questions
    python -m scripts.load_level_questions --language uz
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
    BANK_FILES,
    DEFAULT_BANK_LANGUAGE,
    insert_bank,
    load_bank,
    validate_bank,
)

logger = logging.getLogger(__name__)


async def main(path: Path | None, language: str | None) -> None:
    """Читает банк(и), проверяет их и загружает вопросы в БД."""
    if path is not None:
        banks = [(language or DEFAULT_BANK_LANGUAGE, path)]
    elif language is not None:
        banks = [(language, BANK_FILES[language])]
    else:
        banks = list(BANK_FILES.items())

    session_factory = get_session_factory()
    async with session_factory() as session:
        async with session.begin():
            for bank_language, bank_path in banks:
                questions = load_bank(bank_path)
                counts = validate_bank(questions)
                print(f"[{bank_language}] В банке {len(questions)} вопросов:")
                for level in ("A1", "A2", "B1", "B2", "C1", "C2"):
                    print(f"  {level}: {counts.for_level(level)}")
                stats = await insert_bank(session, questions, language=bank_language)
                print(f"[{bank_language}] Добавлено: {stats.added}, уже было: {stats.skipped}")


if __name__ == "__main__":
    setup_logging()
    parser = argparse.ArgumentParser(description="Загрузить банк вопросов уровня в БД")
    parser.add_argument(
        "--path",
        type=Path,
        default=None,
        help="путь к конкретному JSON-файлу банка (иначе загружаются все известные)",
    )
    parser.add_argument(
        "--language",
        choices=tuple(BANK_FILES),
        default=None,
        help="загрузить только банк одного языка (иначе все)",
    )
    arguments = parser.parse_args()
    asyncio.run(main(arguments.path, arguments.language))
