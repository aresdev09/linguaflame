"""Команда /daily_vocabulary: 20 слов дня с транскрипцией и переводом."""

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.locales import t
from bot.models import User
from bot.services.ai_client import AIClient
from bot.services.ai_errors import AIError
from bot.services.vocabulary import format_daily_vocabulary, get_daily_vocabulary

router = Router(name="daily_vocabulary")


@router.message(Command("daily_vocabulary"))
async def daily_vocabulary_command(
    message: Message,
    user: User,
    session: AsyncSession,
    ai: AIClient,
) -> None:
    """Выдаёт 20 слов на день: сохранённый набор или новый запрос к ИИ."""
    lang = user.native_language
    try:
        daily = await get_daily_vocabulary(session, user.id, ai)
    except AIError as exc:
        await message.answer(t(exc.user_message_key, lang))
        return

    for chunk in format_daily_vocabulary(daily, lang):
        await message.answer(chunk)
