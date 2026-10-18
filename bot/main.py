"""Точка входа бота: запуск в режиме long polling."""

import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.exceptions import TelegramUnauthorizedError

from bot.config import ConfigError, get_settings
from bot.logging_setup import setup_logging

logger = logging.getLogger(__name__)


async def main() -> None:
    """Собирает бота и запускает polling."""
    setup_logging()
    settings = get_settings()
    setup_logging(settings.log_level)

    bot = Bot(token=settings.bot_token)
    dispatcher = Dispatcher()

    logger.info("Бот запускается в режиме long polling")
    try:
        await dispatcher.start_polling(bot)
    finally:
        await bot.session.close()
        logger.info("Бот остановлен")


def run() -> None:
    """Синхронная обёртка для запуска из консоли."""
    try:
        asyncio.run(main())
    except ConfigError as exc:
        logger.error("%s", exc)
        sys.exit(1)
    except TelegramUnauthorizedError:
        logger.error("Telegram отклонил BOT_TOKEN: проверьте токен в .env")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Остановка по Ctrl+C")


if __name__ == "__main__":
    run()
