"""Команды /free_chat и /close_free_chat: разговор с ботом.

Логика ответа — в `bot.services.free_chat`; здесь только Telegram-сценарий:
открытие чата, приём сообщений с индикатором «печатает» и закрытие.

История диалога живёт в FSM (`history`), поэтому `/close_free_chat`
и выход в другой режим очищают её вместе с состоянием.
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
from bot.services.ai_client import AIClient
from bot.services.ai_errors import AIError
from bot.services.free_chat import (
    HISTORY_KEY,
    append_exchange,
    reply_in_chat,
    trim_history,
)
from bot.states import FreeChatStates

logger = logging.getLogger(__name__)

router = Router(name="free_chat")


@router.message(Command("free_chat"))
async def free_chat_command(message: Message, state: FSMContext, user: User) -> None:
    """Открывает свободный разговор и очищает историю прошлого чата."""
    await state.set_state(FreeChatStates.chatting)
    await state.set_data({HISTORY_KEY: []})
    await message.answer(
        t("chat.started", user.native_language), reply_markup=empty_kb()
    )


@router.message(FreeChatStates.chatting, F.text, ~F.text.startswith("/"))
async def free_chat_message(
    message: Message,
    state: FSMContext,
    user: User,
    session: AsyncSession,
    ai: AIClient,
) -> None:
    """Отвечает на сообщение с учётом последних 10 реплик диалога."""
    lang = user.native_language
    text = (message.text or "").strip()
    if not text:
        return

    data = await state.get_data()
    history = trim_history(data.get(HISTORY_KEY))

    await _show_typing(message)
    try:
        answer = await reply_in_chat(session, user, ai, text, history=history)
    except AIError as exc:
        # Чат не закрываем: пользователь может написать ещё раз.
        await message.answer(t(exc.user_message_key, lang))
        return

    await state.update_data(**{HISTORY_KEY: append_exchange(history, text, answer)})
    await message.answer(answer)


@router.message(Command("close_free_chat"))
async def close_free_chat_command(
    message: Message, state: FSMContext, user: User
) -> None:
    """Полностью закрывает чат: состояние и история удаляются.

    Если открыт другой режим, его состояние не трогаем: пользователь
    просил закрыть именно свободный разговор.
    """
    if await state.get_state() != FreeChatStates.chatting.state:
        await message.answer(
            t("chat.not_active", user.native_language), reply_markup=empty_kb()
        )
        return

    await state.clear()
    await message.answer(t("chat.closed", user.native_language), reply_markup=empty_kb())


async def _show_typing(message: Message) -> None:
    """Показывает «печатает», пока ИИ готовит ответ."""
    if message.bot is None:
        return
    try:
        await message.bot.send_chat_action(message.chat.id, ChatAction.TYPING)
    except Exception:  # сбой индикатора не должен ломать разговор
        logger.debug("Не удалось показать индикатор набора текста", exc_info=True)
