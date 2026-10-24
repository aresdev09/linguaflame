"""Репозитории теста уровня: `level_tests` и `level_test_answers`."""

from datetime import datetime

from sqlalchemy import func, select, update

from bot.models import LevelTest, LevelTestAnswer, Question
from bot.repositories.base import BaseRepo


class LevelTestRepo(BaseRepo):
    """Доступ к таблице `level_tests`."""

    async def get(self, test_id: int) -> LevelTest | None:
        return await self.session.get(LevelTest, test_id)

    async def get_active(self, user_id: int) -> LevelTest | None:
        """Незавершённый тест пользователя (последний по времени)."""
        stmt = (
            select(LevelTest)
            .where(LevelTest.user_id == user_id, LevelTest.finished_at.is_(None))
            .order_by(LevelTest.id.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_latest_finished(self, user_id: int) -> LevelTest | None:
        """Последний завершённый тест пользователя — источник текущего уровня."""
        stmt = (
            select(LevelTest)
            .where(LevelTest.user_id == user_id, LevelTest.finished_at.is_not(None))
            .order_by(LevelTest.finished_at.desc(), LevelTest.id.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(
        self,
        user_id: int,
        question_ids: list[int],
        *,
        started_at: datetime | None = None,
    ) -> LevelTest:
        test = LevelTest(user_id=user_id, question_ids=list(question_ids))
        if started_at is not None:
            test.started_at = started_at
        self.session.add(test)
        await self.session.flush()
        return test

    async def finish(
        self,
        test_id: int,
        *,
        score: float,
        total_time_sec: int,
        result_level: str,
        finished_at: datetime,
    ) -> None:
        await self.session.execute(
            update(LevelTest)
            .where(LevelTest.id == test_id)
            .values(
                score=score,
                total_time_sec=total_time_sec,
                result_level=result_level,
                finished_at=finished_at,
            )
        )


class LevelTestAnswerRepo(BaseRepo):
    """Доступ к таблице `level_test_answers`."""

    async def add(
        self,
        test_id: int,
        question_id: int,
        *,
        is_correct: bool,
        answer_time_sec: int,
    ) -> LevelTestAnswer:
        answer = LevelTestAnswer(
            test_id=test_id,
            question_id=question_id,
            is_correct=is_correct,
            answer_time_sec=answer_time_sec,
        )
        self.session.add(answer)
        await self.session.flush()
        return answer

    async def count_for_test(self, test_id: int) -> int:
        stmt = (
            select(func.count())
            .select_from(LevelTestAnswer)
            .where(LevelTestAnswer.test_id == test_id)
        )
        return int(await self.session.scalar(stmt) or 0)

    async def has_answer(self, test_id: int, question_id: int) -> bool:
        stmt = (
            select(func.count())
            .select_from(LevelTestAnswer)
            .where(
                LevelTestAnswer.test_id == test_id,
                LevelTestAnswer.question_id == question_id,
            )
        )
        return bool(await self.session.scalar(stmt))

    async def list_with_questions(self, test_id: int) -> list[tuple[LevelTestAnswer, Question]]:
        """Ответы теста вместе с вопросами, в порядке добавления."""
        stmt = (
            select(LevelTestAnswer, Question)
            .join(Question, Question.id == LevelTestAnswer.question_id)
            .where(LevelTestAnswer.test_id == test_id)
            .order_by(LevelTestAnswer.id)
        )
        result = await self.session.execute(stmt)
        return [(answer, question) for answer, question in result.all()]
