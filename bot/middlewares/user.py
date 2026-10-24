"""Middleware: пользователь из БД кладётся в data["user"]."""

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from sqlalchemy.ext.asyncio import AsyncSession

from bot.middlewares.utils import telegram_user_from
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
        telegram_user = telegram_user_from(event, data)
        if telegram_user is None:
            # Апдейт без пользователя (например, пост в канале)
            return await handler(event, data)

        repo = UserRepo(session)
        # ensure вместо get+create: параллельные апдейты нового пользователя
        # не должны падать на UNIQUE constraint по users.id.
        user, is_new_user = await repo.ensure(
            telegram_user.id,
            username=telegram_user.username,
        )
        if is_new_user:
            logger.info("Новый пользователь: %s", user.id)

        data["user"] = user
        data["is_new_user"] = is_new_user
        return await handler(event, data)
