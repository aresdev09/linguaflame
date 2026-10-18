"""Роутеры бота: по одному роутеру на команду."""

from bot.routers import (
    daily_grammar,
    daily_vocabulary,
    essay_checker,
    free_chat,
    level_detector,
    quiz,
    reminders,
    start,
    stats,
)

__all__ = [
    "daily_grammar",
    "daily_vocabulary",
    "essay_checker",
    "free_chat",
    "level_detector",
    "quiz",
    "reminders",
    "start",
    "stats",
]