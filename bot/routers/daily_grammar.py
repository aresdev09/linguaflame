"""Команда /daily_grammar: пошаговый урок грамматики с мини-тестом.

Логика движка — в `bot.services.grammar`; здесь только Telegram-сценарий:
отправка шагов по одному, приём ответов, вопрос посреди урока и мини-тест.
"""

import asyncio
import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards import (
    GRAMMAR_CONTINUE_CALLBACK,
    GRAMMAR_NEXT_CALLBACK_PREFIX,
    GRAMMAR_RESTART_CALLBACK,
    GRAMMAR_TEST_CALLBACK_PREFIX,
    empty_kb,
    grammar_next_kb,
    grammar_resume_kb,
    grammar_test_kb,
)
from bot.locales import t
from bot.models import Lesson, User
from bot.repositories import LessonRepo
from bot.services import grammar
from bot.services.ai_client import AIClient
from bot.services.ai_errors import AIError
from bot.services.ai_schemas import LessonPlan
from bot.services.streak import register_activity
from bot.states import GrammarStates

logger = logging.getLogger(__name__)

router = Router(name="daily_grammar")

LESSON_ID_KEY = "lesson_id"
STEP_INDEX_KEY = "step_index"
TEST_INDEX_KEY = "test_index"
TEST_CORRECT_KEY = "test_correct"
TEST_MISTAKES_KEY = "test_mistakes"
TEST_ANSWERED_KEY = "test_answered"


@router.message(Command("daily_grammar"))
async def daily_grammar_command(
    message: Message,
    state: FSMContext,
    user: User,
    session: AsyncSession,
    ai: AIClient,
) -> None:
    """Начинает урок или предлагает продолжить незавершённый."""
    lang = user.native_language
    active = await LessonRepo(session).get_active(user.id)
    if active is not None:
        await state.clear()
        if await _offer_resume(message, active, lang=lang):
            return
        # Сохранённый план повреждён: старый урок закроется при создании нового.
    await _start_new_lesson(message, state, user, session, ai, lang=lang)


async def _offer_resume(message: Message, lesson: Lesson, *, lang: str) -> bool:
    """Показывает выбор «продолжить или начать заново». False — план битый."""
    try:
        plan = grammar.load_plan(lesson)
    except AIError:
        logger.warning("Не удалось прочитать план урока %s", lesson.id)
        return False

    steps_total = len(plan.steps)
    if lesson.current_step >= steps_total:
        progress = t("grammar.progress_test", lang)
    else:
        progress = t(
            "grammar.progress_step",
            lang,
            number=lesson.current_step + 1,
            total=steps_total,
        )
    await message.answer(
        t("grammar.resume_prompt", lang, topic=lesson.topic, progress=progress),
        reply_markup=grammar_resume_kb(lang),
    )
    return True


async def _start_new_lesson(
    message: Message,
    state: FSMContext,
    user: User,
    session: AsyncSession,
    ai: AIClient,
    *,
    lang: str,
    status: Message | None = None,
) -> None:
    """Генерирует план урока и отправляет первый шаг."""
    if status is None:
        status = await message.answer(t("grammar.loading", lang))
    else:
        await status.edit_text(t("grammar.loading", lang))
    await state.set_state(GrammarStates.waiting_plan)

    repo = LessonRepo(session)
    previous = await repo.get_active(user.id)
    try:
        lesson, plan = await grammar.create_lesson(session, user, ai)
    except AIError as exc:
        await state.clear()
        try:
            await status.edit_text(t(exc.user_message_key, lang))
        except Exception:  # сообщение могло быть уже удалено
            await message.answer(t(exc.user_message_key, lang))
        return

    if previous is not None:
        # Начать заново можно только с одним активным уроком.
        await repo.update(previous.id, status="done")

    await state.set_state(GrammarStates.in_lesson)
    await state.update_data(
        **{
            LESSON_ID_KEY: lesson.id,
            STEP_INDEX_KEY: 0,
            TEST_ANSWERED_KEY: True,
        }
    )
    prefix = None
    if not user.level:
        prefix = t("grammar.default_level", lang, level=lesson.level)
    await _send_step(
        message, state, lesson, plan, index=0, lang=lang, status=status, prefix=prefix
    )


async def _send_step(
    message: Message,
    state: FSMContext,
    lesson: Lesson,
    plan: LessonPlan,
    *,
    index: int,
    lang: str,
    status: Message | None = None,
    prefix: str | None = None,
    resume: bool = False,
) -> None:
    """Отправляет шаг номер index; первый кусок заменяет сообщение-заглушку."""
    step = plan.steps[index]
    text = grammar.format_step(
        step,
        topic=lesson.topic,
        number=index + 1,
        total=len(plan.steps),
        lang=lang,
    )
    if prefix:
        text = f"{prefix}\n\n{text}"
    chunks = grammar.chunk_text(text)
    markup = None if step.type == "exercise" else grammar_next_kb(index, lang, resume=resume)

    if status is not None:
        await status.edit_text(chunks[0], reply_markup=markup)
    else:
        await message.answer(chunks[0], reply_markup=markup)
    for chunk in chunks[1:]:
        await _sleep_between_messages()
        await message.answer(chunk)

    await state.update_data(**{LESSON_ID_KEY: lesson.id, STEP_INDEX_KEY: index})


async def _advance(
    session: AsyncSession,
    message: Message,
    state: FSMContext,
    lesson: Lesson,
    plan: LessonPlan,
    *,
    next_index: int,
    lang: str,
) -> None:
    """Сохраняет прогресс и показывает следующий шаг или мини-тест."""
    if next_index < len(plan.steps):
        await LessonRepo(session).update(lesson.id, current_step=next_index)
        await _send_step(message, state, lesson, plan, index=next_index, lang=lang)
        return
    await LessonRepo(session).update(lesson.id, current_step=len(plan.steps))
    await _start_final_test(session, message, state, lesson, plan, lang=lang)


async def _start_final_test(
    session: AsyncSession,
    message: Message,
    state: FSMContext,
    lesson: Lesson,
    plan: LessonPlan,
    *,
    lang: str,
    status: Message | None = None,
) -> None:
    """Включает мини-тест: пишет вступление и первый вопрос."""
    await state.set_state(GrammarStates.final_test)
    await state.update_data(
        **{
            LESSON_ID_KEY: lesson.id,
            STEP_INDEX_KEY: -1,
            TEST_INDEX_KEY: 0,
            TEST_CORRECT_KEY: 0,
            TEST_MISTAKES_KEY: [],
            TEST_ANSWERED_KEY: True,
        }
    )
    intro = t("grammar.test_intro", lang, topic=lesson.topic)
    if status is not None:
        await status.edit_text(intro, reply_markup=empty_kb())
    else:
        await message.answer(intro)
    await _send_test_question(message, state, plan, index=0, lang=lang)


async def _send_test_question(
    message: Message,
    state: FSMContext,
    plan: LessonPlan,
    *,
    index: int,
    lang: str,
) -> None:
    """Отправляет вопрос мини-теста с кнопками A, B, C."""
    question = plan.final_test[index]
    await message.answer(
        grammar.format_final_question(
            question, number=index + 1, total=len(plan.final_test), lang=lang
        ),
        reply_markup=grammar_test_kb(index, question.options),
    )
    await state.update_data(**{TEST_INDEX_KEY: index, TEST_ANSWERED_KEY: False})


@router.callback_query(F.data.startswith(GRAMMAR_NEXT_CALLBACK_PREFIX))
async def grammar_next_callback(
    callback: CallbackQuery,
    state: FSMContext,
    user: User,
    session: AsyncSession,
) -> None:
    """Кнопка «Дальше» на шагах explanation и example."""
    lang = user.native_language
    if await state.get_state() != GrammarStates.in_lesson.state:
        await callback.answer(t("grammar.not_active", lang))
        return

    index = _parse_next(callback.data)
    if index is None:
        await callback.answer(t("grammar.invalid_option", lang))
        return

    data = await state.get_data()
    if data.get(STEP_INDEX_KEY) != index:
        # Повторное нажатие на старую кнопку не двигает урок.
        await callback.answer(t("grammar.stale_button", lang))
        return

    lesson = await _load_active_lesson(session, user, data)
    if lesson is None:
        await state.clear()
        await callback.answer(t("grammar.not_active", lang))
        return
    try:
        plan = grammar.load_plan(lesson)
    except AIError as exc:
        await callback.answer(t(exc.user_message_key, lang))
        return
    if index >= len(plan.steps) or plan.steps[index].type == "exercise":
        await callback.answer(t("grammar.stale_button", lang))
        return

    await callback.answer()
    # Блокируем повторные нажатия, пока идёт переход.
    await state.update_data(**{STEP_INDEX_KEY: -1})
    if callback.message is None:
        return
    await _advance(
        session,
        callback.message,
        state,
        lesson,
        plan,
        next_index=index + 1,
        lang=lang,
    )


@router.message(GrammarStates.in_lesson, F.text, ~F.text.startswith("/"))
async def grammar_message(
    message: Message,
    state: FSMContext,
    user: User,
    session: AsyncSession,
    ai: AIClient,
) -> None:
    """Ответ на упражнение или вопрос посреди урока."""
    lang = user.native_language
    text = (message.text or "").strip()
    if not text:
        return

    data = await state.get_data()
    lesson = await _load_active_lesson(session, user, data)
    if lesson is None:
        await state.clear()
        await message.answer(t("grammar.not_active", lang))
        return
    try:
        plan = grammar.load_plan(lesson)
    except AIError as exc:
        await state.clear()
        await message.answer(t(exc.user_message_key, lang))
        return

    index = int(data.get(STEP_INDEX_KEY, 0))
    if index < 0 or index >= len(plan.steps):
        # FSM разошёлся с планом: возвращаемся к сохранённому прогрессу.
        index = lesson.current_step
        if index >= len(plan.steps):
            await _start_final_test(session, message, state, lesson, plan, lang=lang)
            return
    step = plan.steps[index]

    if grammar.is_exercise_answer(step, text):
        is_correct = grammar.check_exercise_answer(step, text)
        if is_correct:
            feedback = t("grammar.exercise_correct", lang)
        else:
            feedback = t("grammar.exercise_wrong", lang, answer=step.answer or "—")
        await message.answer(feedback)
        await _advance(
            session, message, state, lesson, plan, next_index=index + 1, lang=lang
        )
        return

    # Вопрос посреди урока: отвечаем и повторяем текущий шаг, прогресс не меняем.
    try:
        answer = await ai.ask_in_lesson(
            lesson.level,
            lang,
            step_text=grammar.step_context(step),
            question=text,
        )
    except AIError as exc:
        await message.answer(t(exc.user_message_key, lang))
    else:
        await message.answer(answer)
        await message.answer(t("grammar.question_return", lang))
    await _send_step(
        message, state, lesson, plan, index=index, lang=lang, resume=True
    )


@router.message(GrammarStates.final_test, F.text, ~F.text.startswith("/"))
async def grammar_test_message(message: Message, user: User) -> None:
    """В мини-тесте ждём нажатие кнопки, а не текст."""
    await message.answer(t("grammar.test_use_buttons", user.native_language))


@router.callback_query(F.data == GRAMMAR_CONTINUE_CALLBACK)
async def grammar_continue_callback(
    callback: CallbackQuery,
    state: FSMContext,
    user: User,
    session: AsyncSession,
) -> None:
    """Продолжает незавершённый урок с сохранённого шага."""
    lang = user.native_language
    lesson = await LessonRepo(session).get_active(user.id)
    if lesson is None:
        await callback.answer(t("grammar.not_active", lang))
        return
    try:
        plan = grammar.load_plan(lesson)
    except AIError as exc:
        await callback.answer(t(exc.user_message_key, lang))
        return

    await callback.answer()
    if callback.message is None:
        return
    if lesson.current_step < len(plan.steps):
        await state.set_state(GrammarStates.in_lesson)
        await state.update_data(
            **{
                LESSON_ID_KEY: lesson.id,
                STEP_INDEX_KEY: lesson.current_step,
                TEST_ANSWERED_KEY: True,
            }
        )
        await callback.message.edit_text(
            t("grammar.continued", lang, topic=lesson.topic), reply_markup=empty_kb()
        )
        await _send_step(
            callback.message,
            state,
            lesson,
            plan,
            index=lesson.current_step,
            lang=lang,
            resume=True,
        )
        return

    await callback.message.edit_text(
        t("grammar.continued", lang, topic=lesson.topic), reply_markup=empty_kb()
    )
    await _start_final_test(
        session, callback.message, state, lesson, plan, lang=lang
    )


@router.callback_query(F.data == GRAMMAR_RESTART_CALLBACK)
async def grammar_restart_callback(
    callback: CallbackQuery,
    state: FSMContext,
    user: User,
    session: AsyncSession,
    ai: AIClient,
) -> None:
    """Закрывает старый урок и начинает новый по той же команде."""
    lang = user.native_language
    await callback.answer()
    if callback.message is None:
        return
    await _start_new_lesson(
        callback.message, state, user, session, ai, lang=lang, status=callback.message
    )


@router.callback_query(F.data.startswith(GRAMMAR_TEST_CALLBACK_PREFIX))
async def grammar_test_callback(
    callback: CallbackQuery,
    state: FSMContext,
    user: User,
    session: AsyncSession,
) -> None:
    """Ответ на вопрос мини-теста."""
    lang = user.native_language
    if await state.get_state() != GrammarStates.final_test.state:
        await callback.answer(t("grammar.not_active", lang))
        return

    parsed = _parse_test(callback.data)
    if parsed is None:
        await callback.answer(t("grammar.invalid_option", lang))
        return
    index, option = parsed

    data = await state.get_data()
    if data.get(TEST_ANSWERED_KEY) or data.get(TEST_INDEX_KEY) != index:
        await callback.answer(t("grammar.already_answered", lang))
        return

    lesson = await _load_active_lesson(session, user, data)
    if lesson is None:
        await state.clear()
        await callback.answer(t("grammar.not_active", lang))
        return
    try:
        plan = grammar.load_plan(lesson)
    except AIError as exc:
        await callback.answer(t(exc.user_message_key, lang))
        return
    if index >= len(plan.final_test):
        await callback.answer(t("grammar.stale_button", lang))
        return
    question = plan.final_test[index]
    if option not in question.options:
        await callback.answer(t("grammar.invalid_option", lang))
        return

    await callback.answer()
    await state.update_data(**{TEST_ANSWERED_KEY: True})

    correct = int(data.get(TEST_CORRECT_KEY, 0))
    mistakes = [dict(item) for item in data.get(TEST_MISTAKES_KEY, [])]
    if option == question.correct:
        correct += 1
    else:
        mistakes.append(
            {
                "number": index + 1,
                "question": question.question,
                "option": question.correct,
                "answer": question.options[question.correct],
            }
        )
    await state.update_data(**{TEST_CORRECT_KEY: correct, TEST_MISTAKES_KEY: mistakes})

    total = len(plan.final_test)
    if index + 1 >= total:
        # Урок завершён: сначала сохраняем результат, потом показываем его.
        await LessonRepo(session).update(
            lesson.id,
            current_step=len(plan.steps) + total,
            status="done",
        )
        await register_activity(session, user.id, "grammar")
        await state.clear()
        if callback.message is not None:
            await callback.message.edit_text(
                grammar.format_test_result(
                    correct,
                    total,
                    _parse_mistakes(mistakes),
                    topic=lesson.topic,
                    lang=lang,
                ),
                reply_markup=empty_kb(),
            )
        return

    if callback.message is None:
        return
    await callback.message.edit_text(
        grammar.format_test_feedback(question, option, lang=lang),
        reply_markup=empty_kb(),
    )
    await _send_test_question(callback.message, state, plan, index=index + 1, lang=lang)


async def _load_active_lesson(
    session: AsyncSession,
    user: User,
    data: dict,
) -> Lesson | None:
    """Активный урок пользователя из FSM-данных."""
    lesson_id = data.get(LESSON_ID_KEY)
    if not isinstance(lesson_id, int):
        return None
    lesson = await LessonRepo(session).get(lesson_id)
    if lesson is None or lesson.status != "active" or lesson.user_id != user.id:
        return None
    return lesson


def _parse_mistakes(raw: list[dict]) -> list[grammar.Mistake]:
    mistakes = []
    for item in raw:
        try:
            mistakes.append(
                grammar.Mistake(
                    number=int(item["number"]),
                    question=str(item["question"]),
                    option=str(item["option"]),
                    answer=str(item["answer"]),
                )
            )
        except (KeyError, TypeError, ValueError):
            continue
    return mistakes


def _parse_next(data: str | None) -> int | None:
    """Разбирает `grammar:next:<index>`."""
    parts = (data or "").split(":")
    if len(parts) != 3 or parts[0] != "grammar" or parts[1] != "next":
        return None
    try:
        index = int(parts[2])
    except ValueError:
        return None
    return index if index >= 0 else None


def _parse_test(data: str | None) -> tuple[int, str] | None:
    """Разбирает `grammar:test:<index>:<option>`."""
    parts = (data or "").split(":")
    if len(parts) != 4 or parts[0] != "grammar" or parts[1] != "test":
        return None
    try:
        index = int(parts[2])
    except ValueError:
        return None
    option = parts[3]
    if index < 0 or not option:
        return None
    return index, option


async def _sleep_between_messages() -> None:
    """Пауза между автоматическими сообщениями, чтобы не упереться в лимиты."""
    await asyncio.sleep(grammar.AUTO_MESSAGE_DELAY)
