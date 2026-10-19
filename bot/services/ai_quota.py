"""Лимит запросов к ИИ на пользователя в день.

Счётчик хранится в `ai_usage` по локальной дате пользователя. Лимит
считает логические задачи (вопрос квиза, набор слов, урок, проверка эссе,
ответ в чате), а не отдельные HTTP-повторы внутри `AIClient`.

Лимит проверяется до запроса, а счётчик обновляется после успешного
ответа. Так запись в БД не держит блокировку записи SQLite во время
ожидания ответа ИИ — иначе параллельные апдейты падают с
`database is locked`.
"""

import logging
from collections.abc import Iterable, Sequence
from datetime import date, datetime

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
    """Обёртка `AIClient`: не даёт превысить дневной лимит запросов."""

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

    def _day(self) -> date:
        """Локальная дата пользователя, к которой относится запрос."""
        moment = as_utc(self._now)
        timezone_info = resolve_timezone(self._user.timezone, user_id=self._user.id)
        return moment.astimezone(timezone_info).date()

    async def _check_limit(self) -> None:
        """Проверяет лимит до запроса к ИИ; чтение писателей не блокирует."""
        day = self._day()
        usage = await AIUsageRepo(self._session).get(self._user.id, day)
        if usage is not None and usage.requests >= self._limit:
            logger.warning(
                "Лимит ИИ исчерпан: пользователь %s, %s, лимит %d",
                self._user.id,
                day,
                self._limit,
            )
            raise AIQuotaExceeded(f"Пользователь {self._user.id} исчерпал лимит ИИ на {day}")

    async def _count_request(self) -> None:
        """Учитывает запрос после успешного ответа ИИ."""
        await AIUsageRepo(self._session).add(self._user.id, self._day())

    async def generate_quiz(self, level: str, lang: str) -> QuizQuestion:
        await self._check_limit()
        question = await self._client.generate_quiz(level, lang)
        await self._count_request()
        return question

    async def generate_vocabulary(
        self,
        level: str,
        lang: str,
        *,
        count: int,
        exclude_words: Iterable[str] = (),
    ) -> VocabularyResponse:
        await self._check_limit()
        response = await self._client.generate_vocabulary(
            level, lang, count=count, exclude_words=exclude_words
        )
        await self._count_request()
        return response

    async def generate_lesson_plan(
        self,
        level: str,
        lang: str,
        *,
        topic: str | None = None,
    ) -> LessonPlan:
        await self._check_limit()
        plan = await self._client.generate_lesson_plan(level, lang, topic=topic)
        await self._count_request()
        return plan

    async def check_essay(self, level: str, lang: str, text: str) -> EssayCheck:
        await self._check_limit()
        check = await self._client.check_essay(level, lang, text)
        await self._count_request()
        return check

    async def free_chat(
        self,
        level: str,
        lang: str,
        *,
        history: Sequence[dict[str, str]] = (),
        text: str,
    ) -> str:
        await self._check_limit()
        answer = await self._client.free_chat(level, lang, history=history, text=text)
        await self._count_request()
        return answer

    async def ask_in_lesson(
        self,
        level: str,
        lang: str,
        *,
        step_text: str,
        question: str,
    ) -> str:
        await self._check_limit()
        answer = await self._client.ask_in_lesson(
            level, lang, step_text=step_text, question=question
        )
        await self._count_request()
        return answer
