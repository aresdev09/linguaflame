"""Лимит запросов к ИИ на пользователя в день.

Счётчик хранится в `ai_usage` по локальной дате пользователя. Лимит
считает логические задачи (вопрос квиза, набор слов, урок, проверка эссе,
ответ в чате), а не отдельные HTTP-повторы внутри `AIClient`.
"""

import logging
from collections.abc import Iterable, Sequence
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from bot.models import User
from bot.repositories import AIUsageRepo
from bot.services.ai_client import AIClient
from bot.services.ai_errors import AIQuotaExceeded
from bot.services.ai_schemas import (
    EssayCheck,
    LessonPlan,
    QuizQuestion,
    VocabularyResponse,
)
from bot.services.timezones import as_utc, resolve_timezone

logger = logging.getLogger(__name__)


class QuotaAIClient:
    """Обёртка `AIClient`: списывает запрос и не даёт превысить дневной лимит."""

    def __init__(
        self,
        client: AIClient,
        session: AsyncSession,
        user: User,
        limit: int,
        *,
        now: datetime | None = None,
    ) -> None:
        self._client = client
        self._session = session
        self._user = user
        self._limit = limit
        self._now = now

    async def _charge(self) -> None:
        """Списывает один запрос; при исчерпании лимита — понятная ошибка."""
        moment = as_utc(self._now)
        day = moment.astimezone(
            resolve_timezone(self._user.timezone, user_id=self._user.id)
        ).date()
        allowed = await AIUsageRepo(self._session).consume(
            self._user.id, day, self._limit
        )
        if not allowed:
            logger.warning(
                "Лимит ИИ исчерпан: пользователь %s, %s, лимит %d",
                self._user.id,
                day,
                self._limit,
            )
            raise AIQuotaExceeded(
                f"Пользователь {self._user.id} исчерпал лимит ИИ на {day}"
            )

    async def generate_quiz(self, level: str, lang: str) -> QuizQuestion:
        await self._charge()
        return await self._client.generate_quiz(level, lang)

    async def generate_vocabulary(
        self,
        level: str,
        lang: str,
        *,
        count: int,
        exclude_words: Iterable[str] = (),
    ) -> VocabularyResponse:
        await self._charge()
        return await self._client.generate_vocabulary(
            level, lang, count=count, exclude_words=exclude_words
        )

    async def generate_lesson_plan(
        self,
        level: str,
        lang: str,
        *,
        topic: str | None = None,
    ) -> LessonPlan:
        await self._charge()
        return await self._client.generate_lesson_plan(level, lang, topic=topic)

    async def check_essay(self, level: str, lang: str, text: str) -> EssayCheck:
        await self._charge()
        return await self._client.check_essay(level, lang, text)

    async def free_chat(
        self,
        level: str,
        lang: str,
        *,
        history: Sequence[dict[str, str]] = (),
        text: str,
    ) -> str:
        await self._charge()
        return await self._client.free_chat(level, lang, history=history, text=text)

    async def ask_in_lesson(
        self,
        level: str,
        lang: str,
        *,
        step_text: str,
        question: str,
    ) -> str:
        await self._charge()
        return await self._client.ask_in_lesson(
            level, lang, step_text=step_text, question=question
        )
