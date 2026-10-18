"""Ручной запуск проверки напоминаний — один проход без планировщика.

Примеры:
    python -m scripts.run_reminders --offset 11
    REMINDER_HOUR_OFFSET=5 python -m scripts.run_reminders

`--offset` сдвигает «сейчас» на указанное число часов, чтобы увидеть утреннее,
вечернее или пропущенное напоминание, не дожидаясь нужного времени.
"""

import argparse
import asyncio
import sys

from aiogram import Bot

from bot.config import ConfigError, get_settings
from bot.database import get_session_factory
from bot.logging_setup import setup_logging
from bot.scheduler import check_streaks


async def run(offset: int | None) -> int:
    settings = get_settings()
    shift = settings.reminder_hour_offset if offset is None else offset
    bot = Bot(token=settings.bot_token)
    try:
        result = await check_streaks(get_session_factory(), bot, hour_offset=shift)
    finally:
        await bot.session.close()

    print(
        f"Сдвиг {shift:+d} ч: проверено {result.checked}, "
        f"отправлено {result.sent}, пропущено {result.skipped}, "
        f"заблокировали {result.blocked}, ошибок {result.failed}"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Один проход рассылки напоминаний")
    parser.add_argument(
        "--offset",
        type=int,
        default=None,
        help="сдвиг времени в часах (по умолчанию REMINDER_HOUR_OFFSET)",
    )
    args = parser.parse_args()
    try:
        setup_logging(get_settings().log_level)
        return asyncio.run(run(args.offset))
    except ConfigError as exc:
        print(exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
