"""Репозитории: весь доступ к БД идёт только через них."""

from bot.repositories.activity import ActivityRepo
from bot.repositories.base import BaseRepo
from bot.repositories.essay import EssayRepo
from bot.repositories.lesson import LessonRepo
from bot.repositories.question import QuestionRepo
from bot.repositories.streak import StreakRepo
from bot.repositories.user import UserRepo
from bot.repositories.vocabulary import VocabularyRepo

__all__ = [
    "ActivityRepo",
    "BaseRepo",
    "EssayRepo",
    "LessonRepo",
    "QuestionRepo",
    "StreakRepo",
    "UserRepo",
    "VocabularyRepo",
]