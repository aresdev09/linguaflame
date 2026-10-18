"""Репозиторий пользователей."""

from datetime import datetime

from sqlalchemy import select, update

from bot.models import Streak, User
from bot.repositories.base import BaseRepo


class UserRepo(BaseRepo):
    """Доступ к таблице `users`."""

    async def get(self, user_id: int) -> User | None:
        return await self.session.get(User, user_id)

    async def create(
        self,
        user_id: int,
        *,
        username: str | None = None,
        native_language: str = "en",
        timezone: str = "UTC",
    ) -> User:
        """Создаёт нового пользователя (id приходит из Telegram)."""
        user = User(
            id=user_id,
            username=username,
            native_language=native_language,
            timezone=timezone,
        )
        self.session.add(user)
        await self.session.flush()
        return user

    async def list_active_with_streaks(self) -> list[tuple[User, Streak | None]]:
        """Активные пользователи вместе с их серией — кандидаты на напоминание."""
        stmt = (
            select(User, Streak)
            .outerjoin(Streak, Streak.user_id == User.id)
            .where(User.is_active.is_(True))
            .order_by(User.id)
        )
        rows = await self.session.execute(stmt)
        return [(user, streak) for user, streak in rows.all()]

    async def deactivate(self, user_id: int) -> None:
        """Помечает пользователя неактивным (бот заблокирован)."""
        await self.session.execute(update(User).where(User.id == user_id).values(is_active=False))

    async def get_or_create(
        self,
        user_id: int,
        *,
        username: str | None = None,
        native_language: str = "en",
        timezone: str = "UTC",
    ) -> User:
        """Возвращает пользователя, создавая его при первом обращении."""
        user = await self.get(user_id)
        if user is None:
            user = await self.create(
                user_id,
                username=username,
                native_language=native_language,
                timezone=timezone,
            )
        return user

    async def update_profile(
        self,
        user_id: int,
        *,
        username: str | None = None,
        native_language: str | None = None,
        timezone: str | None = None,
    ) -> None:
        """Обновляет профиль; поля, переданные как None, не меняются."""
        values: dict[str, object] = {}
        if username is not None:
            values["username"] = username
        if native_language is not None:
            values["native_language"] = native_language
        if timezone is not None:
            values["timezone"] = timezone
        if values:
            await self.session.execute(update(User).where(User.id == user_id).values(**values))

    async def set_level(self, user_id: int, level: str, tested_at: datetime) -> None:
        """Записывает уровень пользователя.

        Вызывается только из сервиса level detector: больше нигде
        `users.level` не меняется.
        """
        await self.session.execute(
            update(User).where(User.id == user_id).values(level=level, level_tested_at=tested_at)
        )
