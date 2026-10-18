"""Middleware бота: порядок вызова задан в `bot.main`."""

from bot.middlewares.ai import AIClientMiddleware
from bot.middlewares.db import DbSessionMiddleware
from bot.middlewares.errors import ErrorMiddleware
from bot.middlewares.free_chat import FreeChatExitMiddleware
from bot.middlewares.throttle import ThrottleMiddleware
from bot.middlewares.user import UserMiddleware

__all__ = [
    "AIClientMiddleware",
    "DbSessionMiddleware",
    "ErrorMiddleware",
    "FreeChatExitMiddleware",
    "ThrottleMiddleware",
    "UserMiddleware",
]
