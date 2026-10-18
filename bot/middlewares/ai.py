"""Middleware: единый клиент ИИ кладётся в data["ai"]."""

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware

from bot.services.ai_client import AIClient, get_ai_client
from bot.services.ai_quota import QuotaAIClient


class AIClientMiddleware(BaseMiddleware):
    """Передаёт хендлерам клиент ИИ.

    В тестах вместо настоящего клиента подставляется `FakeAIClient`.
    При `daily_limit > 0` клиент оборачивается в `QuotaAIClient`, который
    считает запросы пользователя за его локальный день.
    """

    def __init__(self, client: AIClient | None = None, *, daily_limit: int = 0) -> None:
        self._client = client
        self._daily_limit = daily_limit

    async def __call__(
        self,
        handler: Callable[[Any, dict[str, Any]], Awaitable[Any]],
        event: Any,
        data: dict[str, Any],
    ) -> Any:
        if "ai" not in data:
            client = self._client if self._client is not None else get_ai_client()
            user = data.get("user")
            session = data.get("session")
            if self._daily_limit > 0 and user is not None and session is not None:
                client = QuotaAIClient(client, session, user, self._daily_limit)
            data["ai"] = client
        return await handler(event, data)
