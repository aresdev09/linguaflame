"""Команда /stats: текущая серия дней, рекорд и активность за неделю."""

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.locales import t
from bot.models import User
from bot.services.streak import get_user_stats

router = Router(name="stats")


@router.message(Command("stats"))
async def stats_command(message: Message, user: User, session: AsyncSession) -> None:
    """Показывает прогресс пользователя: серия, рекорд, действия за неделю."""
    stats = await get_user_stats(session, user.id)
    lang = user.native_language
    lines = [
        t("stats.title", lang),
        t("stats.current", lang, days=stats.current_streak),
        t("stats.best", lang, days=stats.best_streak),
        t("stats.week", lang, count=stats.activities_week),
    ]
    if stats.current_streak == 0:
        lines.append(t("stats.hint", lang))
    await message.answer("\n".join(lines))
