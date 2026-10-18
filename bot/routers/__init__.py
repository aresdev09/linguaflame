"""Роутеры бота: по одному роутеру на команду."""

from bot.routers import daily_grammar, daily_vocabulary, level_detector, quiz, start, stats

__all__ = [
    "daily_grammar",
    "daily_vocabulary",
    "level_detector",
    "quiz",
    "start",
    "stats",
]