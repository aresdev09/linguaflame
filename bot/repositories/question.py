"""Репозиторий банка вопросов."""

from collections.abc import Iterable

from sqlalchemy import select

from bot.models import Question
from bot.repositories.base import BaseRepo


class QuestionRepo(BaseRepo):
    """Доступ к таблице `questions`."""

    async def get(self, question_id: int) -> Question | None:
        return await self.session.get(Question, question_id)

    async def create(
        self,
        *,
        kind: str,
        level: str,
        text: str,
        options: dict[str, str],
        correct_option: str,
        explanation: str | None = None,
    ) -> Question:
        question = Question(
            kind=kind,
            level=level,
            text=text,
            options=options,
            correct_option=correct_option,
            explanation=explanation,
        )
        self.session.add(question)
        await self.session.flush()
        return question

    async def list_by_kind_level(
        self,
        kind: str | None = None,
        level: str | None = None,
        *,
        limit: int | None = None,
        exclude_ids: Iterable[int] = (),
    ) -> list[Question]:
        """Вопросы по виду и уровню без повторов."""
        stmt = select(Question)
        if kind is not None:
            stmt = stmt.where(Question.kind == kind)
        if level is not None:
            stmt = stmt.where(Question.level == level)
        excluded = list(exclude_ids)
        if excluded:
            stmt = stmt.where(Question.id.not_in(excluded))
        stmt = stmt.order_by(Question.id)
        if limit is not None:
            stmt = stmt.limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())