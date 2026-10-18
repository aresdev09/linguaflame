"""Репозиторий лога активности."""

from datetime import datetime

from sqlalchemy import func, select

from bot.models import ActivityLog
from bot.repositories.base import BaseRepo


class ActivityRepo(BaseRepo):
    """Доступ к таблице `activity_log`."""

    async def add(
        self,
        user_id: int,
        kind: str,
        *,
        created_at: datetime | None = None,
    ) -> ActivityLog:
        """Пишет действие в лог; момент можно подменить (нужно тестам)."""
        entry = ActivityLog(user_id=user_id, kind=kind)
        if created_at is not None:
            entry.created_at = created_at
        self.session.add(entry)
        await self.session.flush()
        return entry

    async def count_since(self, user_id: int, since: datetime) -> int:
        """Сколько действий пользователь совершил начиная с момента `since`."""
        stmt = (
            select(func.count())
            .select_from(ActivityLog)
            .where(
                ActivityLog.user_id == user_id,
                ActivityLog.created_at >= since,
            )
        )
        return int(await self.session.scalar(stmt) or 0)