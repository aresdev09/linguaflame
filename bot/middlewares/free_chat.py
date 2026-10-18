"""Middleware: команда другого режима закрывает свободный чат.

Правило: команды других режимов во время чата
сначала закрывают его. Сделано middleware, а не фильтрами в каждом роутере,
чтобы не дублировать одно правило шесть раз.
"""

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware

from bot.services.free_chat import command_name
from bot.states import FreeChatStates

# Команду закрытия обрабатывает свой хендлер: ему нужен текущий статус чата.
CLOSE_COMMAND = "close_free_chat"


class FreeChatExitMiddleware(BaseMiddleware):
    """Сбрасывает состояние чата, если пришла команда любого другого режима."""

    async def __call__(
        self,
        handler: Callable[[Any, dict[str, Any]], Awaitable[Any]],
        event: Any,
        data: dict[str, Any],
    ) -> Any:
        name = command_name(getattr(event, "text", None))
        state = data.get("state")
        if (
            name is not None
            and name != CLOSE_COMMAND
            and state is not None
            and await state.get_state() == FreeChatStates.chatting.state
        ):
            await state.clear()
        return await handler(event, data)
