"""Репозиторий проверок эссе."""

from sqlalchemy import select

from bot.models import Essay
from bot.repositories.base import BaseRepo


class EssayRepo(BaseRepo):
    """Доступ к таблице `essays`."""

    async def create(
        self,
        *,
        user_id: int,
        text: str,
        score_overall: float,
        score_json: dict,
        feedback: str,
    ) -> Essay:
        essay = Essay(
            user_id=user_id,
            text=text,
            score_overall=score_overall,
            score_json=score_json,
            feedback=feedback,
        )
        self.session.add(essay)
        await self.session.flush()
        return essay

    async def get(self, essay_id: int) -> Essay | None:
        return await self.session.get(Essay, essay_id)

    async def list_by_user(self, user_id: int, limit: int = 10) -> list[Essay]:
        """История проверок, сначала свежие."""
        stmt = (
            select(Essay)
            .where(Essay.user_id == user_id)
            .order_by(Essay.created_at.desc(), Essay.id.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
