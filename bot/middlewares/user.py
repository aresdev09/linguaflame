"""Middleware: пользователь из БД кладётся в data["user"]."""

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models import User
from bot.repositories import UserRepo

logger = logging.getLogger(__name__)


class UserMiddleware(BaseMiddleware):
    """Подгружает пользователя, создавая его при первом обращении.

    В data кладёт `user` и `is_new_user`: онбординг показывается только новым.
    """

    async def __call__(
        self,
        handler: Callable[[Any, dict[str, Any]], Awaitable[Any]],
        event: Any,
        data: dict[str, Any],
    ) -> Any:
        session: AsyncSession = data["session"]
        telegram_user = event.from_user

        repo = UserRepo(session)
        user: User | None = await repo.get(telegram_user.id)
        is_new_user = user is None
        if is_new_user:
            user = await repo.create(telegram_user.id, username=telegram_user.username)
            logger.info("Новый пользователь: %s", user.id)

        data["user"] = user
        data["is_new_user"] = is_new_user
        return await handler(event, data)