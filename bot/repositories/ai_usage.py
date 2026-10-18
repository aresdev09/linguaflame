"""Репозиторий счётчика запросов к ИИ по дням."""

from datetime import date

from bot.models import AIUsage
from bot.repositories.base import BaseRepo


class AIUsageRepo(BaseRepo):
    """Доступ к таблице `ai_usage`."""

    async def get(self, user_id: int, day: date) -> AIUsage | None:
        return await self.session.get(AIUsage, (user_id, day))

    async def consume(self, user_id: int, day: date, limit: int) -> bool:
        """Списывает один запрос; False — дневной лимит уже исчерпан."""
        usage = await self.get(user_id, day)
        if usage is None:
            usage = AIUsage(user_id=user_id, day=day, requests=1)
            self.session.add(usage)
            await self.session.flush()
            return True
        if usage.requests >= limit:
            return False
        usage.requests += 1
        await self.session.flush()
        return True
