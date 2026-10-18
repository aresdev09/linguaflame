"""Middleware: необработанные ошибки не роняют бота."""

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware

from bot.locales import t

logger = logging.getLogger(__name__)


class ErrorMiddleware(BaseMiddleware):
    """Ловит исключения, пишет их в лог и отвечает пользователю."""

    async def __call__(
        self,
        handler: Callable[[Any, dict[str, Any]], Awaitable[Any]],
        event: Any,
        data: dict[str, Any],
    ) -> Any:
        try:
            return await handler(event, data)
        except Exception:
            logger.exception("Необработанная ошибка при обработке апдейта")
            user = data.get("user")
            await self._notify(event, t("common.error", getattr(user, "native_language", None)))
            return None

    async def _notify(self, event: Any, text: str) -> None:
        """Отвечает на сообщение или показывает тост на кнопке."""
        answer = getattr(event, "answer", None)
        if answer is None:
            return
        try:
            await answer(text)
        except Exception:
            logger.exception("Не удалось отправить сообщение об ошибке")