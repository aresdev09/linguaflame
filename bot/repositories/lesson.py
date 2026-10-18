"""Репозиторий уроков."""

from sqlalchemy import select, update

from bot.models import Lesson
from bot.repositories.base import BaseRepo


class LessonRepo(BaseRepo):
    """Доступ к таблице `lessons`."""

    async def create(
        self, *, user_id: int, topic: str, level: str, plan: dict
    ) -> Lesson:
        lesson = Lesson(user_id=user_id, topic=topic, level=level, plan=plan)
        self.session.add(lesson)
        await self.session.flush()
        return lesson

    async def get(self, lesson_id: int) -> Lesson | None:
        return await self.session.get(Lesson, lesson_id)

    async def get_active(self, user_id: int) -> Lesson | None:
        """Последний незавершённый урок пользователя."""
        stmt = (
            select(Lesson)
            .where(Lesson.user_id == user_id, Lesson.status == "active")
            .order_by(Lesson.id.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def update(
        self,
        lesson_id: int,
        *,
        current_step: int | None = None,
        status: str | None = None,
    ) -> None:
        """Сохраняет прогресс урока; поля, переданные как None, не меняются."""
        values: dict[str, object] = {}
        if current_step is not None:
            values["current_step"] = current_step
        if status is not None:
            values["status"] = status
        if values:
            await self.session.execute(
                update(Lesson).where(Lesson.id == lesson_id).values(**values)
            )