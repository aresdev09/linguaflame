"""Middleware: единый клиент ИИ кладётся в data["ai"]."""

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware

from bot.services.ai_client import AIClient, get_ai_client


class AIClientMiddleware(BaseMiddleware):
    """Передаёт хендлерам клиент ИИ.

    В тестах вместо настоящего клиента подставляется `FakeAIClient`.
    """

    def __init__(self, client: AIClient | None = None) -> None:
        self._client = client

    async def __call__(
        self,
        handler: Callable[[Any, dict[str, Any]], Awaitable[Any]],
        event: Any,
        data: dict[str, Any],
    ) -> Any:
        if "ai" not in data:
            data["ai"] = self._client if self._client is not None else get_ai_client()
        return await handler(event, data)
