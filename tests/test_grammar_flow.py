"""Сценарные тесты команды /daily_grammar."""

import inspect
from datetime import datetime, timezone
from typing import Any

from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.storage.base import StorageKey
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.locales import t
from bot.middlewares.ai import AIClientMiddleware
from bot.middlewares.user import UserMiddleware
from bot.models import ActivityLog, Lesson
from bot.repositories import UserRepo
from bot.routers.daily_grammar import daily_grammar_command, grammar_message
from bot.services.ai_errors import AIRequestError
from bot.services.fake_ai_client import FakeAIClient
from bot.services.grammar_topics import GRAMMAR_TOPICS
from bot.states import GrammarStates
from tests.fakes import FakeCallbackQuery, FakeChat, FakeMessage, FakeUpdate

USER_ID = 904
SAMARKAND = "Asia/Samarkand"


def make_state(user_id: int) -> FSMContext:
    key = StorageKey(bot_id=1, chat_id=user_id, user_id=user_id)
    return FSMContext(MemoryStorage(), key)


def as_aiogram_caller(handler: Any) -> Any:
    async def caller(event: Any, data: dict[str, Any]) -> Any:
        params = inspect.signature(handler).parameters
        kwargs = {key: value for key, value in data.items() if key in params}
        return await handler(event, **kwargs)

    return caller


async def _dispatch(
    session_factory: async_sessionmaker[AsyncSession],
    handler: Any,
    event: Any,
    state: FSMContext,
    ai: FakeAIClient | None = None,
) -> None:
    ai_middleware = AIClientMiddleware(client=ai)
    user_middleware = UserMiddleware()
    caller = as_aiogram_caller(handler)

    async def on_handler(update: Any, data: dict[str, Any]) -> Any:
        return await caller(event, data)

    async def on_ai(update: Any, data: dict[str, Any]) -> Any:
        return await user_middleware(on_handler, update, data)

    async with session_factory() as session:
        async with session.begin():
            data = {
                "session": session,
                "state": state,
                "event_from_user": event.from_user,
            }
            await ai_middleware(on_ai, FakeUpdate(event), data)


async def _create_user(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    level: str | None = "B1",
    native_language: str = "ru",
) -> None:
    async with session_factory() as session:
        async with session.begin():
            repo = UserRepo(session)
            await repo.create(
                USER_ID,
                native_language=native_language,
                timezone=SAMARKAND,
            )
            if level is not None:
                await repo.set_level(USER_ID, level, datetime.now(timezone.utc))


async def _lessons(session_factory: async_sessionmaker[AsyncSession]) -> list[Lesson]:
    async with session_factory() as session:
        result = await session.execute(select(Lesson).order_by(Lesson.id))
        return list(result.scalars().all())


async def _activity_count(session_factory: async_sessionmaker[AsyncSession]) -> int:
    async with session_factory() as session:
        result = await session.execute(select(ActivityLog))
        return len(list(result.scalars().all()))


def _last_message(chat: FakeChat) -> FakeMessage:
    return FakeMessage(chat, len(chat.messages) - 1)


def _callbacks(markup: Any) -> list[str]:
    return [button.callback_data for row in markup.inline_keyboard for button in row]


async def _start(
    session_factory: async_sessionmaker[AsyncSession],
    chat: FakeChat,
    state: FSMContext,
    ai: FakeAIClient,
) -> None:
    await _dispatch(session_factory, daily_grammar_command, FakeMessage(chat), state, ai)


async def _click(
    session_factory: async_sessionmaker[AsyncSession],
    chat: FakeChat,
    state: FSMContext,
    ai: FakeAIClient,
    data: str,
    message: FakeMessage | None = None,
) -> FakeCallbackQuery:
    callback = FakeCallbackQuery(data, message or _last_message(chat))
    await _dispatch(session_factory, _callback_handler(data), callback, state, ai)
    return callback


def _callback_handler(data: str) -> Any:
    """Берёт из роутера подходящий хендлер callback-кнопки."""
    from bot.routers import daily_grammar

    if data == "grammar:continue":
        return daily_grammar.grammar_continue_callback
    if data == "grammar:restart":
        return daily_grammar.grammar_restart_callback
    if data.startswith("grammar:next:"):
        return daily_grammar.grammar_next_callback
    if data.startswith("grammar:test:"):
        return daily_grammar.grammar_test_callback
    raise AssertionError(f"Неизвестная кнопка: {data}")


async def _send_text(
    session_factory: async_sessionmaker[AsyncSession],
    chat: FakeChat,
    state: FSMContext,
    ai: FakeAIClient,
    text: str,
) -> None:
    message = FakeMessage(chat)
    message.text = text
    await _dispatch(session_factory, grammar_message, message, state, ai)


async def _advance_to_exercise(
    session_factory: async_sessionmaker[AsyncSession],
    chat: FakeChat,
    state: FSMContext,
    ai: FakeAIClient,
) -> None:
    """Доводит урок до шага exercise: два нажатия «Дальше»."""
    await _click(session_factory, chat, state, ai, "grammar:next:0")
    await _click(session_factory, chat, state, ai, "grammar:next:1")


async def test_start_lesson_saves_plan_and_sends_first_step(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _create_user(session_factory, level="B1")
    ai = FakeAIClient()
    chat = FakeChat(USER_ID)
    state = make_state(USER_ID)

    await _start(session_factory, chat, state, ai)

    assert len(chat.messages) == 1  # заглушка «Готовлю урок» заменена первым шагом
    assert GRAMMAR_TOPICS["B1"][0] in chat.messages[-1]
    assert "шаг 1 из 3" in chat.messages[-1]
    assert _callbacks(chat.markups[-1]) == ["grammar:next:0"]
    assert await state.get_state() == GrammarStates.in_lesson.state

    lessons = await _lessons(session_factory)
    assert len(lessons) == 1
    lesson = lessons[0]
    assert lesson.status == "active"
    assert lesson.current_step == 0
    assert lesson.level == "B1"
    # Тема выбирается из списка уровня, а не из ответа ИИ.
    assert lesson.topic == GRAMMAR_TOPICS["B1"][0]
    assert len(lesson.plan["steps"]) == 3
    assert len(lesson.plan["final_test"]) == 5

    calls = ai.calls_of("lesson_plan")
    assert calls[0]["level"] == "B1"
    assert calls[0]["topic"] == GRAMMAR_TOPICS["B1"][0]
    assert calls[0]["lang"] == "ru"


async def test_next_button_moves_steps_and_saves_progress(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _create_user(session_factory)
    ai = FakeAIClient()
    chat = FakeChat(USER_ID)
    state = make_state(USER_ID)
    await _start(session_factory, chat, state, ai)

    await _click(session_factory, chat, state, ai, "grammar:next:0")

    lessons = await _lessons(session_factory)
    assert lessons[0].current_step == 1
    assert "шаг 2 из 3" in chat.messages[-1]
    assert _callbacks(chat.markups[-1]) == ["grammar:next:1"]

    await _click(session_factory, chat, state, ai, "grammar:next:1")

    lessons = await _lessons(session_factory)
    assert lessons[0].current_step == 2
    # Шаг exercise ждёт текстовый ответ, кнопки ему не нужны.
    assert "упражнение 3 из 3" in chat.messages[-1]
    assert chat.markups[-1] is None


async def test_exercise_answer_advances_to_final_test(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _create_user(session_factory)
    ai = FakeAIClient()
    chat = FakeChat(USER_ID)
    state = make_state(USER_ID)
    await _start(session_factory, chat, state, ai)
    await _advance_to_exercise(session_factory, chat, state, ai)

    await _send_text(session_factory, chat, state, ai, "goes")

    assert t("grammar.exercise_correct", "ru") in chat.messages
    assert "🏁 Мини-тест" in chat.messages[-1]
    assert await state.get_state() == GrammarStates.final_test.state
    lessons = await _lessons(session_factory)
    assert lessons[0].current_step == 3
    assert _callbacks(chat.markups[-1]) == [
        "grammar:test:0:A",
        "grammar:test:0:B",
        "grammar:test:0:C",
    ]


async def test_wrong_exercise_answer_shows_correct_one(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _create_user(session_factory)
    ai = FakeAIClient()
    chat = FakeChat(USER_ID)
    state = make_state(USER_ID)
    await _start(session_factory, chat, state, ai)
    await _advance_to_exercise(session_factory, chat, state, ai)

    await _send_text(session_factory, chat, state, ai, "go")

    assert t("grammar.exercise_wrong", "ru", answer="goes") in chat.messages
    lessons = await _lessons(session_factory)
    assert lessons[0].current_step == 3


async def test_question_mid_lesson_does_not_move_step(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _create_user(session_factory)
    ai = FakeAIClient()
    chat = FakeChat(USER_ID)
    state = make_state(USER_ID)
    await _start(session_factory, chat, state, ai)
    await _advance_to_exercise(session_factory, chat, state, ai)

    await _send_text(session_factory, chat, state, ai, "Почему здесь goes?")

    calls = ai.calls_of("lesson_question")
    assert len(calls) == 1
    assert calls[0]["question"] == "Почему здесь goes?"
    assert calls[0]["step_text"] == "Exercise: He ___ to work by bus."
    assert calls[0]["level"] == "B1"
    # После ответа ИИ урок повторяет тот же шаг и прогресс не сдвигается.
    assert "упражнение 3 из 3" in chat.messages[-1]
    assert t("grammar.question_return", "ru") in chat.messages
    data = await state.get_data()
    assert data["step_index"] == 2
    assert await state.get_state() == GrammarStates.in_lesson.state
    lessons = await _lessons(session_factory)
    assert lessons[0].current_step == 2

    await _send_text(session_factory, chat, state, ai, "goes")
    lessons = await _lessons(session_factory)
    assert lessons[0].current_step == 3


async def test_full_lesson_with_mini_test_registers_activity(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _create_user(session_factory)
    ai = FakeAIClient()
    chat = FakeChat(USER_ID)
    state = make_state(USER_ID)
    await _start(session_factory, chat, state, ai)
    await _advance_to_exercise(session_factory, chat, state, ai)
    await _send_text(session_factory, chat, state, ai, "goes")

    # Отвечаем на 5 вопросов: верно, неверно, верно, верно, верно.
    answers = ["B", "C", "B", "A", "B"]
    for index, option in enumerate(answers):
        await _click(session_factory, chat, state, ai, f"grammar:test:{index}:{option}")

    result = chat.messages[-1]
    assert "4 из 5" in result
    assert "Разбор ошибок" in result
    assert "They ___ football every Sunday." in result
    assert "A) play" in result

    lessons = await _lessons(session_factory)
    assert lessons[0].status == "done"
    assert await _activity_count(session_factory) == 1
    assert await state.get_state() is None


async def test_resume_unfinished_lesson(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _create_user(session_factory)
    ai = FakeAIClient()
    chat = FakeChat(USER_ID)
    state = make_state(USER_ID)
    await _start(session_factory, chat, state, ai)
    await _click(session_factory, chat, state, ai, "grammar:next:0")

    await _start(session_factory, chat, state, ai)

    prompt = chat.messages[-1]
    assert GRAMMAR_TOPICS["B1"][0] in prompt
    assert "шаге 2 из 3" in prompt
    assert _callbacks(chat.markups[-1]) == ["grammar:continue", "grammar:restart"]

    await _click(session_factory, chat, state, ai, "grammar:continue")

    assert "шаг 2 из 3" in chat.messages[-1]
    assert await state.get_state() == GrammarStates.in_lesson.state
    lessons = await _lessons(session_factory)
    assert len(lessons) == 1
    assert lessons[0].current_step == 1


async def test_restart_closes_old_lesson_and_picks_new_topic(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _create_user(session_factory)
    ai = FakeAIClient()
    chat = FakeChat(USER_ID)
    state = make_state(USER_ID)
    await _start(session_factory, chat, state, ai)
    await _click(session_factory, chat, state, ai, "grammar:next:0")

    await _start(session_factory, chat, state, ai)
    await _click(session_factory, chat, state, ai, "grammar:restart")

    lessons = await _lessons(session_factory)
    assert len(lessons) == 2
    assert lessons[0].status == "done"
    assert lessons[1].status == "active"
    assert lessons[1].topic != lessons[0].topic
    assert lessons[1].topic == GRAMMAR_TOPICS["B1"][1]
    assert await state.get_state() == GrammarStates.in_lesson.state


async def test_level_comes_from_db_and_defaults_when_absent(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _create_user(session_factory, level=None)
    ai = FakeAIClient()
    chat = FakeChat(USER_ID)
    state = make_state(USER_ID)

    await _start(session_factory, chat, state, ai)

    calls = ai.calls_of("lesson_plan")
    assert calls[0]["level"] == "A2"
    assert t("grammar.default_level", "ru", level="A2") in chat.messages[-1]
    lessons = await _lessons(session_factory)
    assert lessons[0].level == "A2"


async def test_ai_error_on_plan_shows_message_and_clears_state(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _create_user(session_factory)
    ai = FakeAIClient(error=AIRequestError("ИИ недоступен"))
    chat = FakeChat(USER_ID)
    state = make_state(USER_ID)

    await _start(session_factory, chat, state, ai)

    assert chat.messages[-1] == t("common.ai_unavailable", "ru")
    assert await state.get_state() is None
    assert await _lessons(session_factory) == []


async def test_double_next_click_does_not_skip_step(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _create_user(session_factory)
    ai = FakeAIClient()
    chat = FakeChat(USER_ID)
    state = make_state(USER_ID)
    await _start(session_factory, chat, state, ai)
    first_step_message = _last_message(chat)

    await _click(session_factory, chat, state, ai, "grammar:next:0", first_step_message)
    second = await _click(session_factory, chat, state, ai, "grammar:next:0", first_step_message)

    assert second.answers == [t("grammar.stale_button", "ru")]
    lessons = await _lessons(session_factory)
    assert lessons[0].current_step == 1


async def test_text_in_final_test_asks_for_buttons(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    from bot.routers.daily_grammar import grammar_test_message

    await _create_user(session_factory)
    ai = FakeAIClient()
    chat = FakeChat(USER_ID)
    state = make_state(USER_ID)
    await _start(session_factory, chat, state, ai)
    await _advance_to_exercise(session_factory, chat, state, ai)
    await _send_text(session_factory, chat, state, ai, "goes")

    message = FakeMessage(chat)
    message.text = "B"
    await _dispatch(session_factory, grammar_test_message, message, state, ai)

    assert chat.messages[-1] == t("grammar.test_use_buttons", "ru")
