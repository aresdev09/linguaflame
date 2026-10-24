"""Репозиторий серий дней."""

from datetime import date

from sqlalchemy import update
from sqlalchemy.exc import IntegrityError

from bot.models import Streak
from bot.repositories.base import BaseRepo


class StreakRepo(BaseRepo):
    """Доступ к таблице `streaks`."""

    async def get(self, user_id: int) -> Streak | None:
        return await self.session.get(Streak, user_id)

    async def get_or_create(self, user_id: int) -> Streak:
        """Серия пользователя, создаётся при первом обращении.

        Безопасно к гонке: если параллельный апдейт успел создать серию,
        вернётся уже существующая.
        """
        streak = await self.get(user_id)
        if streak is not None:
            return streak
        try:
            # Savepoint: неудачная вставка не ломает общую транзакцию апдейта.
            async with self.session.begin_nested():
                streak = Streak(user_id=user_id, current_streak=0, best_streak=0)
                self.session.add(streak)
                await self.session.flush()
            return streak
        except IntegrityError:
            existing = await self.get(user_id)
            if existing is None:
                raise
            return existing

    async def set_progress(
        self,
        user_id: int,
        *,
        current_streak: int,
        best_streak: int,
        last_activity_date: date,
    ) -> None:
        """Записывает серию после учебного действия."""
        streak = await self.get_or_create(user_id)
        streak.current_streak = current_streak
        streak.best_streak = best_streak
        streak.last_activity_date = last_activity_date
        await self.session.flush()

    async def update(self, user_id: int, **fields: object) -> None:
        """Обновляет переданные поля серии (current_streak, best_streak, ...)."""
        if not fields:
            return
        await self.session.execute(update(Streak).where(Streak.user_id == user_id).values(**fields))
