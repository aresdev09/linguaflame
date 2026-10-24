"""Ручная установка или сброс уровня пользователя.

Обычно `users.level` меняет только /level_detector; скрипт нужен для
поддержки: исправить ошибочный результат теста или вернуть пользователя
к повторной сдаче.
Запуск из корня проекта:
    python -m scripts.set_user_level --telegram-id 123456789 --level a2
    python -m scripts.set_user_level --telegram-id 123456789 --reset
"""

import argparse
import asyncio
import sys
from datetime import UTC, datetime
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bot.config import LEVELS
from bot.database import get_session_factory
from bot.logging_setup import setup_logging
from bot.repositories import UserRepo


async def main(telegram_id: int, level: str | None, reset: bool) -> int:
    """Меняет уровень пользователя; возвращает код выхода процесса."""
    session_factory = get_session_factory()
    async with session_factory() as session:
        async with session.begin():
            repo = UserRepo(session)
            user = await repo.get(telegram_id)
            if user is None:
                print(f"Пользователь {telegram_id} не найден")
                return 1

            old_level = user.level or "—"
            if reset:
                await repo.reset_level(telegram_id)
                new_level = "—"
            else:
                assert level is not None
                await repo.set_level(telegram_id, level, datetime.now(UTC))
                new_level = level

    print(f"Пользователь {telegram_id}: уровень {old_level} → {new_level}")
    if reset:
        print("Уровень очищен: следующая команда /level_detector начнётся заново.")
    return 0


if __name__ == "__main__":
    setup_logging()
    parser = argparse.ArgumentParser(
        description="Установить или сбросить уровень пользователя (для поддержки)"
    )
    parser.add_argument(
        "--telegram-id",
        type=int,
        required=True,
        help="id пользователя в Telegram",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--level",
        type=str.upper,
        choices=LEVELS,
        help="новый уровень: A1, A2, B1, B2, C1 или C2",
    )
    group.add_argument(
        "--reset",
        action="store_true",
        help="полностью сбросить уровень, чтобы пользователь прошёл тест заново",
    )
    arguments = parser.parse_args()
    raise SystemExit(asyncio.run(main(arguments.telegram_id, arguments.level, arguments.reset)))
