"""Кнопка быстрого старта под напоминанием: 5 слов и серия снова растёт."""

import logging

from aiogram import F, Router
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards import REMINDER_QUICK_CALLBACK, empty_kb
from bot.locales import t
from bot.models import User
from bot.services.ai_client import AIClient
from bot.services.ai_errors import AIError
from bot.services.reminders import QUICK_START_WORDS, format_quick_words
from bot.services.streak import register_activity
from bot.services.vocabulary import DEFAULT_LEVEL

logger = logging.getLogger(__name__)

router = Router(name="reminders")


@router.callback_query(F.data == REMINDER_QUICK_CALLBACK)
async def quick_start_callback(
    callback: CallbackQuery,
    user: User,
    session: AsyncSession,
    ai: AIClient,
) -> None:
    """Показывает 5 слов по уровню и засчитывает учебное действие."""
    lang = user.native_language
    try:
        response = await ai.generate_vocabulary(
            user.level or DEFAULT_LEVEL,
            lang,
            count=QUICK_START_WORDS,
        )
    except AIError as exc:
        await callback.answer(t(exc.user_message_key, lang), show_alert=True)
        return

    words = response.words[:QUICK_START_WORDS]
    if not words:
        await callback.answer(t("common.ai_bad_answer", lang), show_alert=True)
        return

    await register_activity(session, user.id, "vocabulary")
    await callback.answer()
    if callback.message is not None:
        await callback.message.answer(
            format_quick_words(words, lang), reply_markup=empty_kb()
        )
