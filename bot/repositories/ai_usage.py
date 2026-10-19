"""Репозиторий счётчика запросов к ИИ по дням."""

from datetime import date

from bot.models import AIUsage
from bot.repositories.base import BaseRepo


class AIUsageRepo(BaseRepo):
    """Доступ к таблице `ai_usage`."""

    async def get(self, user_id: int, day: date) -> AIUsage | None:
        return await self.session.get(AIUsage, (user_id, day))

    async def add(self, user_id: int, day: date) -> None:
        """Учитывает один запрос за день, создавая счётчик при необходимости."""
        usage = await self.get(user_id, day)
        if usage is None:
            usage = AIUsage(user_id=user_id, day=day, requests=1)
            self.session.add(usage)
        else:
            usage.requests += 1
        await self.session.flush()
