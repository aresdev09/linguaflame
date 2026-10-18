"""Репозиторий наборов слов на день."""

from datetime import date

from sqlalchemy import select

from bot.models import VocabularySet
from bot.repositories.base import BaseRepo


class VocabularyRepo(BaseRepo):
    """Доступ к таблице `vocabulary_sets`."""

    async def get_by_date(self, user_id: int, day: date) -> VocabularySet | None:
        """Набор слов за конкретный календарный день пользователя."""
        stmt = (
            select(VocabularySet)
            .where(VocabularySet.user_id == user_id, VocabularySet.date == day)
            .order_by(VocabularySet.id.desc())
            .limit(1)
        )
        return await self.session.scalar(stmt)

    async def save(
        self,
        user_id: int,
        day: date,
        words: list[dict[str, object]],
    ) -> VocabularySet:
        """Сохраняет набор слов за день."""
        entry = VocabularySet(user_id=user_id, date=day, words=words)
        self.session.add(entry)
        await self.session.flush()
        return entry

    async def recent_words(self, user_id: int, since: date) -> list[str]:
        """Слова из наборов начиная с даты `since` — чтобы не повторяться."""
        stmt = select(VocabularySet.words).where(
            VocabularySet.user_id == user_id,
            VocabularySet.date >= since,
        )
        rows = await self.session.scalars(stmt)
        words: list[str] = []
        for chunk in rows:
            for item in chunk or []:
                if isinstance(item, dict):
                    word = item.get("word")
                    if isinstance(word, str) and word.strip():
                        words.append(word.strip())
        return words
