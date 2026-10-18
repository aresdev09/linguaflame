"""Команда /quiz: вопросы по одному с кнопками A, B, C и итогом."""

import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards import (
    QUIZ_CALLBACK_PREFIX,
    QUIZ_FINISH_CALLBACK,
    empty_kb,
    quiz_options_kb,
)
from bot.locales import t
from bot.models import User
from bot.repositories import QuestionRepo
from bot.services.ai_client import AIClient
from bot.services.ai_errors import AIError
from bot.services.quiz import (
    format_quiz_feedback,
    format_quiz_question,
    format_quiz_result,
    next_quiz_question,
    score_quiz_answer,
)
from bot.services.streak import register_activity, streak_line
from bot.states import QuizStates

logger = logging.getLogger(__name__)

router = Router(name="quiz")

QUESTION_ID_KEY = "question_id"
CORRECT_COUNT_KEY = "correct_count"
ANSWERED_COUNT_KEY = "answered_count"
USED_IDS_KEY = "used_ids"
ANSWERED_KEY = "answered"


@router.message(Command("quiz"))
async def quiz_command(
    message: Message,
    state: FSMContext,
    user: User,
    session: AsyncSession,
    ai: AIClient,
) -> None:
    """Начинает новую сессию квиза и присылает первый вопрос."""
    lang = user.native_language
    await state.set_state(QuizStates.answering)
    await state.update_data(
        **{
            QUESTION_ID_KEY: None,
            CORRECT_COUNT_KEY: 0,
            ANSWERED_COUNT_KEY: 0,
            USED_IDS_KEY: [],
            # Пока вопроса нет, отвечать не на что: старые кнопки не сработают.
            ANSWERED_KEY: True,
        }
    )
    status = await message.answer(t("quiz.loading", lang))
    await _send_question(message, state, user, session, ai, lang=lang, status=status)


async def _send_question(
    message: Message,
    state: FSMContext,
    user: User,
    session: AsyncSession,
    ai: AIClient,
    *,
    lang: str,
    status: Message | None = None,
) -> None:
    """Берёт следующий вопрос и заменяет им сообщение-заглушку."""
    data = await state.get_data()
    used_ids = list(data.get(USED_IDS_KEY, []))
    number = int(data.get(ANSWERED_COUNT_KEY, 0)) + 1
    if status is None:
        status = await message.answer(t("quiz.loading", lang))

    try:
        question = await next_quiz_question(session, user, ai, used_ids=used_ids)
    except AIError as exc:
        await state.clear()
        await status.edit_text(t(exc.user_message_key, lang))
        return

    await state.update_data(
        **{
            QUESTION_ID_KEY: question.id,
            USED_IDS_KEY: [*used_ids, question.id],
            ANSWERED_KEY: False,
        }
    )
    await status.edit_text(
        format_quiz_question(question, number, lang),
        reply_markup=quiz_options_kb(question.id, question.options, lang),
    )


@router.callback_query(F.data.startswith(QUIZ_CALLBACK_PREFIX))
async def quiz_callback(
    callback: CallbackQuery,
    state: FSMContext,
    user: User,
    session: AsyncSession,
    ai: AIClient,
) -> None:
    """Ответ на вопрос или завершение квиза. `callback.answer()` — на всех путях."""
    lang = user.native_language
    if await state.get_state() != QuizStates.answering.state:
        await callback.answer(t("quiz.not_active", lang))
        return

    if callback.data == QUIZ_FINISH_CALLBACK:
        await callback.answer()
        await _finish_quiz(callback, state, session, user, lang)
        return

    parsed = _parse_answer(callback.data)
    if parsed is None:
        await callback.answer(t("quiz.invalid_option", lang))
        return
    question_id, option = parsed

    data = await state.get_data()
    if data.get(ANSWERED_KEY) or data.get(QUESTION_ID_KEY) != question_id:
        # Повторное нажатие на уже отвеченный вопрос не засчитывается.
        await callback.answer(t("quiz.already_answered", lang))
        return

    question = await QuestionRepo(session).get(question_id)
    if question is None or option not in question.options:
        await callback.answer(t("quiz.invalid_option", lang))
        return

    await callback.answer()
    # Сразу закрываем вопрос от повторных нажатий, до запросов к БД и ИИ.
    await state.update_data(**{ANSWERED_KEY: True})

    score = score_quiz_answer(
        question,
        option,
        correct_count=int(data.get(CORRECT_COUNT_KEY, 0)),
        answered_count=int(data.get(ANSWERED_COUNT_KEY, 0)),
    )
    await state.update_data(
        **{
            CORRECT_COUNT_KEY: score.correct_count,
            ANSWERED_COUNT_KEY: score.answered_count,
        }
    )
    await register_activity(session, user.id, "quiz")

    if callback.message is None:
        await state.clear()
        return

    await callback.message.edit_text(
        format_quiz_feedback(question, is_correct=score.is_correct, lang=lang),
        reply_markup=empty_kb(),
    )
    await _send_question(callback.message, state, user, session, ai, lang=lang)


async def _finish_quiz(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    user: User,
    lang: str,
) -> None:
    """Показывает итог с серией дней и закрывает сессию."""
    data = await state.get_data()
    correct_count = int(data.get(CORRECT_COUNT_KEY, 0))
    answered_count = int(data.get(ANSWERED_COUNT_KEY, 0))
    await state.clear()

    if callback.message is None:
        return
    text = format_quiz_result(
        correct_count=correct_count,
        answered_count=answered_count,
        lang=lang,
    )
    if answered_count:
        text = f"{text}\n\n{await streak_line(session, user.id, lang)}"
    await callback.message.edit_text(text, reply_markup=empty_kb())


def _parse_answer(data: str | None) -> tuple[int, str] | None:
    """Разбирает `quiz:<id>:<option>`; всё остальное — неверный callback."""
    if not data:
        return None
    parts = data.split(":")
    if len(parts) != 3 or parts[0] != "quiz":
        return None
    try:
        question_id = int(parts[1])
    except ValueError:
        return None
    option = parts[2]
    if not option:
        return None
    return question_id, option
