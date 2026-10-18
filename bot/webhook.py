"""Режим webhook: приём апдейтов через aiohttp.

Polling остаётся режимом по умолчанию (`BOT_MODE=polling`). Webhook нужен,
когда хостинг не даёт держать исходящее соединение или требует HTTPS-эндпоинт:
бот поднимает HTTP-сервер, а Telegram сам присылает апдейты.
"""

import asyncio
import logging
import signal

from aiogram import Bot, Dispatcher
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web

from bot.config import Settings

logger = logging.getLogger(__name__)


def build_webhook_app(bot: Bot, dispatcher: Dispatcher, settings: Settings) -> web.Application:
    """Собирает aiohttp-приложение с обработчиком апдейтов Telegram."""
    app = web.Application()
    handler = SimpleRequestHandler(
        dispatcher=dispatcher,
        bot=bot,
        secret_token=settings.webhook_secret or None,
    )
    handler.register(app, path=settings.webhook_path)
    setup_application(app, dispatcher, bot=bot)
    return app


async def run_webhook(bot: Bot, dispatcher: Dispatcher, settings: Settings) -> None:
    """Запускает HTTP-сервер и регистрирует webhook в Telegram."""
    app = build_webhook_app(bot, dispatcher, settings)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, settings.webhook_host, settings.webhook_port)
    await site.start()

    await bot.set_webhook(
        url=settings.webhook_url,
        secret_token=settings.webhook_secret or None,
        allowed_updates=dispatcher.resolve_used_update_types(),
        drop_pending_updates=True,
    )
    logger.info(
        "Webhook: %s (слушаю %s:%d)",
        settings.webhook_url,
        settings.webhook_host,
        settings.webhook_port,
    )

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop_event.set)
        except (NotImplementedError, RuntimeError):
            # Windows и некоторые встраиваемые циклы не поддерживают сигналы.
            pass

    try:
        await stop_event.wait()
    finally:
        await bot.delete_webhook(drop_pending_updates=False)
        await runner.cleanup()
        logger.info("Webhook остановлен")
