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
    status = await message.answer(t("vocabulary.loading", lang))
    try:
        daily = await get_daily_vocabulary(session, user.id, ai)
    except AIError as exc:
        await status.edit_text(t(exc.user_message_key, lang))
        return

    chunks = format_daily_vocabulary(daily, lang)
    await status.edit_text(chunks[0])
    for chunk in chunks[1:]:
        await message.answer(chunk)
