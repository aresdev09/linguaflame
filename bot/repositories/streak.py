"""Репозиторий серий дней."""

from sqlalchemy import update

from bot.models import Streak
from bot.repositories.base import BaseRepo


class StreakRepo(BaseRepo):
    """Доступ к таблице `streaks`."""

    async def get(self, user_id: int) -> Streak | None:
        return await self.session.get(Streak, user_id)

    async def get_or_create(self, user_id: int) -> Streak:
        streak = await self.get(user_id)
        if streak is None:
            streak = Streak(user_id=user_id, current_streak=0, best_streak=0)
            self.session.add(streak)
            await self.session.flush()
        return streak

    async def update(self, user_id: int, **fields: object) -> None:
        """Обновляет переданные поля серии (current_streak, best_streak, ...)."""
        if not fields:
            return
        await self.session.execute(
            update(Streak).where(Streak.user_id == user_id).values(**fields)
        )