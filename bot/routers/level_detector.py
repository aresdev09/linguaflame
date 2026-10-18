"""Команда /level_detector: тест из 50 вопросов с определением уровня.

Правила:
- `users.level` меняется только после полностью завершённого теста;
- незавершённый тест можно продолжить с того же вопроса;
- повторная сдача начинается после подтверждения с текущим уровнем и датой.
"""

import logging
from datetime import datetime, timezone

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards import (
    LEVEL_CALLBACK_PREFIX,
    LEVEL_CANCEL_CALLBACK,
    LEVEL_START_CALLBACK,
    empty_kb,
    level_retake_kb,
    level_test_options_kb,
)
from bot.locales import t
from bot.models import LevelTest, Question, User
from bot.repositories import (
    LevelTestAnswerRepo,
    LevelTestRepo,
    QuestionRepo,
    UserRepo,
)
from bot.services.level_test import (
    InsufficientQuestionsError,
    LevelTestResult,
    LevelAnswer,
    compute_level_test_result,
    format_level_question,
    format_level_result,
    format_retake_prompt,
    get_questions_by_ids,
    select_test_questions,
)
from bot.services.streak import register_activity, streak_line
from bot.states import LevelTestStates

logger = logging.getLogger(__name__)

router = Router(name="level_detector")

TEST_ID_KEY = "test_id"
QUESTION_ID_KEY = "question_id"
ANSWERED_COUNT_KEY = "answered_count"
ANSWERED_KEY = "answered"
SENT_AT_KEY = "sent_at"


@router.message(Command("level_detector"))
async def level_detector_command(
    message: Message,
    state: FSMContext,
    user: User,
    session: AsyncSession,
) -> None:
    """Продолжает незавершённый тест или предлагает начать новый."""
    lang = user.native_language
    active = await LevelTestRepo(session).get_active(user.id)

    if active is not None:
        await state.set_state(LevelTestStates.answering)
        await _resume_test(message, state, user, session, active, lang=lang)
        return

    await state.clear()
    if user.level:
        await message.answer(
            format_retake_prompt(user, lang),
            reply_markup=level_retake_kb(lang),
        )
        return

    await _start_new_test(message, state, user, session, lang=lang)


async def _start_new_test(
    message: Message,
    state: FSMContext,
    user: User,
    session: AsyncSession,
    *,
    lang: str,
    send_intro: bool = True,
) -> None:
    """Создаёт тест из 50 вопросов и отправляет первый вопрос."""
    try:
        questions = await select_test_questions(session)
    except InsufficientQuestionsError as exc:
        logger.warning("Тест уровня недоступен: %s", exc)
        await message.answer(t("level.bank_empty", lang))
        await state.clear()
        return

    test = await LevelTestRepo(session).create(user.id, [question.id for question in questions])
    await state.set_state(LevelTestStates.answering)
    if send_intro:
        await message.answer(t("level.intro", lang))
    await _ask_question(
        message,
        state,
        test=test,
        question=questions[0],
        index=0,
        lang=lang,
    )


async def _resume_test(
    message: Message,
    state: FSMContext,
    user: User,
    session: AsyncSession,
    test: LevelTest,
    *,
    lang: str,
) -> None:
    """Продолжает тест с первого неотвеченного вопроса."""
    question_ids = list(test.question_ids or [])
    total = len(question_ids)
    if total == 0:
        await message.answer(t("level.bank_empty", lang))
        await state.clear()
        return

    answers_count = await LevelTestAnswerRepo(session).count_for_test(test.id)
    if answers_count >= total:
        result = await _complete_test(session, test, user)
        await state.clear()
        if result is not None:
            await message.answer(
                await _result_text(session, result, user, lang),
                reply_markup=empty_kb(),
            )
        return

    next_index = answers_count
    question = (await get_questions_by_ids(session, [question_ids[next_index]]))[0]
    await state.set_state(LevelTestStates.answering)
    await message.answer(t("level.resume", lang, number=next_index + 1, total=total))
    await _ask_question(
        message,
        state,
        test=test,
        question=question,
        index=next_index,
        lang=lang,
    )


async def _ask_question(
    message: Message,
    state: FSMContext,
    *,
    test: LevelTest,
    question: Question,
    index: int,
    lang: str,
) -> None:
    """Показывает вопрос и запоминает момент отправки для учёта скорости."""
    total = len(test.question_ids)
    await state.update_data(
        **{
            TEST_ID_KEY: test.id,
            QUESTION_ID_KEY: question.id,
            ANSWERED_COUNT_KEY: index,
            ANSWERED_KEY: False,
            SENT_AT_KEY: datetime.now(timezone.utc).isoformat(),
        }
    )
    await message.answer(
        format_level_question(question, index + 1, total, lang),
        reply_markup=level_test_options_kb(question.id, question.options),
    )


@router.callback_query(F.data.startswith(LEVEL_CALLBACK_PREFIX))
async def level_callback(
    callback: CallbackQuery,
    state: FSMContext,
    user: User,
    session: AsyncSession,
) -> None:
    """Старт/отмена теста или ответ на вопрос. `callback.answer()` — на всех путях."""
    lang = user.native_language

    if callback.data == LEVEL_START_CALLBACK:
        await _handle_start(callback, state, user, session, lang=lang)
        return
    if callback.data == LEVEL_CANCEL_CALLBACK:
        await callback.answer()
        await state.clear()
        if callback.message is not None:
            await callback.message.edit_text(t("level.canceled", lang), reply_markup=empty_kb())
        return

    await _handle_answer(callback, state, user, session, lang=lang)


async def _handle_start(
    callback: CallbackQuery,
    state: FSMContext,
    user: User,
    session: AsyncSession,
    *,
    lang: str,
) -> None:
    """Начинает новый тест или продолжает уже идущий (двойной клик)."""
    if callback.message is None:
        await callback.answer(t("level.not_active", lang))
        return

    active = await LevelTestRepo(session).get_active(user.id)
    if active is not None:
        if await state.get_state() == LevelTestStates.answering.state:
            await callback.answer(t("level.already_running", lang))
            return
        await callback.answer()
        await state.set_state(LevelTestStates.answering)
        await _resume_test(callback.message, state, user, session, active, lang=lang)
        return

    await callback.answer()
    await callback.message.edit_text(t("level.intro", lang), reply_markup=empty_kb())
    await _start_new_test(
        callback.message,
        state,
        user,
        session,
        lang=lang,
        send_intro=False,
    )


async def _handle_answer(
    callback: CallbackQuery,
    state: FSMContext,
    user: User,
    session: AsyncSession,
    *,
    lang: str,
) -> None:
    """Записывает ответ и присылает следующий вопрос или результат."""
    if await state.get_state() != LevelTestStates.answering.state:
        await callback.answer(t("level.not_active", lang))
        return

    parsed = _parse_answer(callback.data)
    if parsed is None:
        await callback.answer(t("level.invalid_option", lang))
        return
    question_id, option = parsed

    data = await state.get_data()
    if data.get(ANSWERED_KEY, True) or data.get(QUESTION_ID_KEY) != question_id:
        # Повторный клик по отвеченному вопросу не засчитывается.
        await callback.answer(t("level.already_answered", lang))
        return

    test_id = data.get(TEST_ID_KEY)
    test = await LevelTestRepo(session).get(int(test_id)) if test_id else None
    if test is None or test.user_id != user.id or test.finished_at is not None:
        await callback.answer(t("level.not_active", lang))
        return

    question_ids = list(test.question_ids or [])
    answered_count = int(data.get(ANSWERED_COUNT_KEY, 0))
    if answered_count >= len(question_ids) or question_ids[answered_count] != question_id:
        await callback.answer(t("level.invalid_option", lang))
        return

    question = await QuestionRepo(session).get(question_id)
    if question is None or option not in question.options:
        await callback.answer(t("level.invalid_option", lang))
        return

    await callback.answer()
    # Сразу закрываем вопрос от повторных нажатий, до записей в БД.
    await state.update_data(**{ANSWERED_KEY: True})

    now = datetime.now(timezone.utc)
    answer_time = _elapsed_seconds(data.get(SENT_AT_KEY), now)
    is_correct = option == question.correct_option
    await LevelTestAnswerRepo(session).add(
        test.id,
        question_id,
        is_correct=is_correct,
        answer_time_sec=answer_time,
    )

    new_count = answered_count + 1
    total = len(question_ids)
    await state.update_data(**{ANSWERED_COUNT_KEY: new_count})

    if callback.message is None:
        return

    if new_count >= total:
        result = await _complete_test(session, test, user)
        await state.clear()
        if result is None:
            await callback.message.edit_text(t("level.bank_empty", lang), reply_markup=empty_kb())
            return
        await callback.message.edit_text(
            await _result_text(session, result, user, lang),
            reply_markup=empty_kb(),
        )
        return

    await callback.message.edit_text(
        t("level.answer_saved", lang, number=new_count, total=total),
        reply_markup=empty_kb(),
    )
    next_question = (await get_questions_by_ids(session, [question_ids[new_count]]))[0]
    await _ask_question(
        callback.message,
        state,
        test=test,
        question=next_question,
        index=new_count,
        lang=lang,
    )


async def _complete_test(
    session: AsyncSession,
    test: LevelTest,
    user: User,
    *,
    now: datetime | None = None,
) -> LevelTestResult | None:
    """Считает результат и записывает уровень — только после полного теста."""
    if test.finished_at is not None:
        return None

    rows = await LevelTestAnswerRepo(session).list_with_questions(test.id)
    if not rows or len(rows) < len(test.question_ids):
        return None

    answers = [
        LevelAnswer(
            level=question.level,
            kind=question.kind,
            is_correct=answer.is_correct,
            answer_time_sec=answer.answer_time_sec,
        )
        for answer, question in rows
    ]
    result = compute_level_test_result(answers)

    moment = now or datetime.now(timezone.utc)
    await LevelTestRepo(session).finish(
        test.id,
        score=result.percent,
        total_time_sec=result.total_time_sec,
        result_level=result.level,
        finished_at=moment,
    )
    await UserRepo(session).set_level(user.id, result.level, moment)
    await register_activity(session, user.id, "level_test", now=moment)
    return result


async def _result_text(
    session: AsyncSession,
    result: LevelTestResult,
    user: User,
    lang: str,
) -> str:
    """Итог теста и текущая серия дней."""
    return (
        f"{format_level_result(result, lang)}\n\n{t('level.result_done', lang)}"
        f"\n\n{await streak_line(session, user.id, lang)}"
    )


def _elapsed_seconds(sent_at_raw: object, now: datetime) -> int:
    """Секунды между отправкой вопроса и ответом (не меньше нуля)."""
    if not isinstance(sent_at_raw, str) or not sent_at_raw:
        return 0
    try:
        sent_at = datetime.fromisoformat(sent_at_raw)
    except ValueError:
        return 0
    if sent_at.tzinfo is None:
        sent_at = sent_at.replace(tzinfo=timezone.utc)
    return max(0, int((now - sent_at).total_seconds()))


def _parse_answer(data: str | None) -> tuple[int, str] | None:
    """Разбирает `level:<question_id>:<option>`; start/cancel сюда не попадают."""
    if not data:
        return None
    parts = data.split(":")
    if len(parts) != 3 or parts[0] != "level":
        return None
    try:
        question_id = int(parts[1])
    except ValueError:
        return None
    option = parts[2]
    if option not in {"A", "B", "C", "D"}:
        return None
    return question_id, option
