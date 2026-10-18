"""Команда /essay_checker: проверка эссе по критериям IELTS.

Логика проверки — в `bot.services.essay`; здесь только Telegram-сценарий:
просьба прислать текст, проверка длины, ожидание ответа ИИ и разбор.
"""

import logging

from aiogram import F, Router
from aiogram.enums import ChatAction
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards import empty_kb
from bot.locales import t
from bot.models import User
from bot.services import essay
from bot.services.ai_client import AIClient
from bot.services.ai_errors import AIError
from bot.states import EssayStates

logger = logging.getLogger(__name__)

router = Router(name="essay_checker")


@router.message(Command("essay_checker"))
async def essay_checker_command(message: Message, state: FSMContext, user: User) -> None:
    """Просит прислать эссе и переводит диалог в ожидание текста."""
    lang = user.native_language
    await state.set_state(EssayStates.waiting_text)
    await message.answer(
        t(
            "essay.prompt",
            lang,
            min_words=essay.MIN_WORDS,
            max_words=essay.MAX_WORDS,
        ),
        reply_markup=empty_kb(),
    )


@router.message(EssayStates.waiting_text, F.text, ~F.text.startswith("/"))
async def essay_text_handler(
    message: Message,
    state: FSMContext,
    user: User,
    session: AsyncSession,
    ai: AIClient,
) -> None:
    """Проверяет присланное эссе и отправляет разбор."""
    lang = user.native_language
    try:
        text = essay.prepare_essay(message.text or "")
    except essay.EssayLengthError as exc:
        # Состояние не сбрасываем: пользователь может прислать текст ещё раз.
        await message.answer(
            t(
                exc.user_message_key,
                lang,
                words=exc.words,
                min_words=essay.MIN_WORDS,
                max_words=essay.MAX_WORDS,
            )
        )
        return

    status = await message.answer(t("essay.loading", lang))
    await _show_typing(message)
    try:
        result = await essay.check_essay(session, user, ai, text)
    except AIError as exc:
        await state.clear()
        await status.edit_text(t(exc.user_message_key, lang))
        return

    await state.clear()
    chunks = result.feedback
    await status.edit_text(chunks[0], parse_mode="HTML", reply_markup=empty_kb())
    for chunk in chunks[1:]:
        await message.answer(chunk, parse_mode="HTML")


async def _show_typing(message: Message) -> None:
    """Показывает «печатает», пока ИИ проверяет эссе."""
    if message.bot is None:
        return
    try:
        await message.bot.send_chat_action(message.chat.id, ChatAction.TYPING)
    except Exception:  # сбой индикатора не должен ломать проверку
        logger.debug("Не удалось показать индикатор набора текста", exc_info=True)
