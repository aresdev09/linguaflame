"""Подключение к базе данных: async engine и фабрика сессий."""

from functools import lru_cache

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from bot.config import get_settings


@lru_cache
def get_engine() -> AsyncEngine:
    """Создаёт (однократно) async-движок по `DATABASE_URL`."""
    settings = get_settings()
    return create_async_engine(settings.database_url, pool_pre_ping=True)


@lru_cache
def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Фабрика сессий; объекты не истекают после commit."""
    return async_sessionmaker(get_engine(), expire_on_commit=False)
