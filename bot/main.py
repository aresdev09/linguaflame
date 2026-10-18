"""Точка входа бота: запуск в режиме long polling."""

import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.exceptions import TelegramUnauthorizedError
from aiogram.fsm.storage.base import BaseStorage
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.types import BotCommand

from bot.config import ConfigError, Settings, get_settings
from bot.database import get_session_factory
from bot.locales import DEFAULT_LANGUAGE, t
from bot.logging_setup import setup_logging
from bot.middlewares import (
    DbSessionMiddleware,
    ErrorMiddleware,
    ThrottleMiddleware,
    UserMiddleware,
)
from bot.routers import start, stats

logger = logging.getLogger(__name__)

# Команды меню Telegram: (команда, ключ описания в локализации)
COMMANDS: tuple[tuple[str, str], ...] = (
    ("start", "commands.start"),
    ("stats", "commands.stats"),
    ("quiz", "commands.quiz"),
    ("daily_vocabulary", "commands.daily_vocabulary"),
    ("daily_grammar", "commands.daily_grammar"),
    ("essay_checker", "commands.essay_checker"),
    ("level_detector", "commands.level_detector"),
    ("free_chat", "commands.free_chat"),
    ("close_free_chat", "commands.close_free_chat"),
)


def build_dispatcher(storage: BaseStorage) -> Dispatcher:
    """Собирает диспетчер: роутеры и порядок middleware."""
    dispatcher = Dispatcher(storage=storage)
    dispatcher.include_router(start.router)
    dispatcher.include_router(stats.router)

    # Порядок важен: ошибки ловим снаружи, сессия БД открывается до хендлера.
    dispatcher.update.outer_middleware(ErrorMiddleware())
    dispatcher.update.middleware(DbSessionMiddleware(get_session_factory()))
    dispatcher.update.middleware(UserMiddleware())
    dispatcher.update.middleware(ThrottleMiddleware())
    return dispatcher


async def build_storage(settings: Settings) -> BaseStorage:
    """Redis для FSM, а если Redis недоступен — память процесса."""
    try:
        storage = RedisStorage.from_url(
            settings.redis_url, socket_connect_timeout=1, socket_timeout=1
        )
        await storage.redis.ping()
    except Exception:
        logger.warning(
            "Redis недоступен (%s), FSM работает в памяти процесса",
            settings.redis_url,
        )
        return MemoryStorage()
    logger.info("FSM: Redis (%s)", settings.redis_url)
    return storage


async def setup_commands(bot: Bot) -> None:
    """Публикует список команд в меню бота."""
    await bot.set_my_commands(
        [
            BotCommand(command=command, description=t(key, DEFAULT_LANGUAGE))
            for command, key in COMMANDS
        ]
    )


async def main() -> None:
    setup_logging()
    settings = get_settings()
    setup_logging(settings.log_level)

    bot = Bot(token=settings.bot_token)
    dispatcher = build_dispatcher(await build_storage(settings))

    try:
        await setup_commands(bot)
    except Exception:
        logger.exception("Не удалось обновить список команд")

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