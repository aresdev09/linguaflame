"""Middleware: защита от спама."""

import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware

logger = logging.getLogger(__name__)

DEFAULT_RATE_LIMIT = 1.0
_PRUNE_THRESHOLD = 1000
_MAX_IDLE_SECONDS = 3600.0


class ThrottleMiddleware(BaseMiddleware):
    """Не больше одного сообщения в секунду на пользователя.

    Лишние апдейты молча отбрасываются. Счётчики живут в памяти процесса,
    при нескольких инстансах лимит считается в рамках одного инстанса.
    """

    def __init__(
        self,
        rate_limit: float = DEFAULT_RATE_LIMIT,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self.rate_limit = rate_limit
        self._monotonic = monotonic
        self._last_seen: dict[int, float] = {}

    async def __call__(
        self,
        handler: Callable[[Any, dict[str, Any]], Awaitable[Any]],
        event: Any,
        data: dict[str, Any],
    ) -> Any:
        user = data.get("user")
        user_id = user.id if user is not None else event.from_user.id
        now = self._monotonic()

        last_seen = self._last_seen.get(user_id)
        if last_seen is not None and now - last_seen < self.rate_limit:
            logger.debug("Апдейт от %s отброшен антиспамом", user_id)
            return None

        self._last_seen[user_id] = now
        if len(self._last_seen) > _PRUNE_THRESHOLD:
            self._prune(now)
        return await handler(event, data)

    def _prune(self, now: float) -> None:
        """Забывает пользователей, которые давно не писали."""
        self._last_seen = {
            user_id: seen
            for user_id, seen in self._last_seen.items()
            if now - seen < _MAX_IDLE_SECONDS
        }