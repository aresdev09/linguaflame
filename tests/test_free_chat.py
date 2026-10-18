"""Сценарные тесты /free_chat и /close_free_chat."""

import inspect
from datetime import UTC, datetime
from typing import Any

from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.locales import t
from bot.middlewares.ai import AIClientMiddleware
from bot.middlewares.free_chat import FreeChatExitMiddleware
from bot.middlewares.user import UserMiddleware
from bot.models import ActivityLog, Streak
from bot.repositories import UserRepo
from bot.routers.free_chat import (
    close_free_chat_command,
    free_chat_command,
    free_chat_message,
)
from bot.routers.quiz import quiz_command
from bot.services.ai_errors import AITimeoutError
from bot.services.fake_ai_client import DEFAULT_CHAT_ANSWER, FakeAIClient
from bot.services.free_chat import HISTORY_KEY, HISTORY_LIMIT, append_exchange, trim_history
from bot.states import FreeChatStates, QuizStates
from tests.fakes import FakeChat, FakeMessage, FakeUpdate

USER_ID = 2002
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
    ai: Any,
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
            await repo.create(USER_ID, native_language=native_language, timezone=SAMARKAND)
            if level is not None:
                await repo.set_level(USER_ID, level, datetime.now(UTC))


class FakeBot:
    """Бот, запоминающий chat actions."""

    def __init__(self) -> None:
        self.actions: list[tuple[int, str]] = []

    async def send_chat_action(self, chat_id: int, action: Any) -> None:
        self.actions.append((chat_id, action))


async def _open(
    session_factory: async_sessionmaker[AsyncSession],
    chat: FakeChat,
    state: FSMContext,
    ai: Any,
) -> None:
    await _dispatch(session_factory, free_chat_command, FakeMessage(chat), state, ai)


async def _send(
    session_factory: async_sessionmaker[AsyncSession],
    chat: FakeChat,
    state: FSMContext,
    ai: Any,
    text: str,
) -> None:
    message = FakeMessage(chat)
    message.text = text
    await _dispatch(session_factory, free_chat_message, message, state, ai)


async def _close(
    session_factory: async_sessionmaker[AsyncSession],
    chat: FakeChat,
    state: FSMContext,
    ai: Any,
) -> None:
    await _dispatch(session_factory, close_free_chat_command, FakeMessage(chat), state, ai)


async def _history(state: FSMContext) -> list[dict[str, str]]:
    return (await state.get_data()).get(HISTORY_KEY, [])


async def _chat_activities(session_factory: async_sessionmaker[AsyncSession]) -> list[ActivityLog]:
    async with session_factory() as session:
        result = await session.execute(select(ActivityLog).where(ActivityLog.kind == "chat"))
        return list(result.scalars().all())


# --- 11.1 вход и 11.4 индикатор -------------------------------------------


async def test_free_chat_command_opens_chat_with_empty_history(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _create_user(session_factory)
    chat = FakeChat(USER_ID)
    state = make_state(USER_ID)

    await _open(session_factory, chat, state, FakeAIClient())

    assert await state.get_state() == FreeChatStates.chatting.state
    assert await _history(state) == []
    assert chat.messages[-1] == t("chat.started", "ru")


async def test_free_chat_command_resets_history_from_previous_chat(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _create_user(session_factory)
    chat = FakeChat(USER_ID)
    state = make_state(USER_ID)
    await state.set_data(
        {HISTORY_KEY: [{"role": "user", "content": "old"}, {"role": "assistant", "content": "old"}]}
    )

    await _open(session_factory, chat, state, FakeAIClient())

    assert await _history(state) == []


async def test_typing_action_is_shown_while_waiting(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _create_user(session_factory)
    chat = FakeChat(USER_ID)
    chat.bot = FakeBot()
    state = make_state(USER_ID)
    ai = FakeAIClient()

    await _open(session_factory, chat, state, ai)
    await _send(session_factory, chat, state, ai, "Hello!")

    assert chat.bot.actions == [(USER_ID, "typing")]


# --- 11.2 ответы и 11.3 история -------------------------------------------


async def test_reply_uses_level_language_and_saves_history(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _create_user(session_factory)
    chat = FakeChat(USER_ID)
    state = make_state(USER_ID)
    ai = FakeAIClient()

    await _open(session_factory, chat, state, ai)
    await _send(session_factory, chat, state, ai, "Hi, I from Uzbekistan")

    call = ai.calls_of("free_chat")[-1]
    assert call["level"] == "B1"
    assert call["lang"] == "ru"
    assert call["text"] == "Hi, I from Uzbekistan"
    assert call["history"] == []
    assert chat.messages[-1] == DEFAULT_CHAT_ANSWER
    assert await _history(state) == [
        {"role": "user", "content": "Hi, I from Uzbekistan"},
        {"role": "assistant", "content": DEFAULT_CHAT_ANSWER},
    ]


async def test_history_is_passed_to_ai_and_keeps_last_ten_messages(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _create_user(session_factory)
    chat = FakeChat(USER_ID)
    state = make_state(USER_ID)
    ai = FakeAIClient()
    await _open(session_factory, chat, state, ai)

    total = HISTORY_LIMIT // 2 + 2  # 7 обменов → 14 сообщений
    for number in range(total):
        await _send(session_factory, chat, state, ai, f"message {number}")

    stored = await _history(state)
    assert len(stored) == HISTORY_LIMIT
    assert stored[-1] == {"role": "assistant", "content": DEFAULT_CHAT_ANSWER}

    last_call = ai.calls_of("free_chat")[-1]
    # В ИИ уходят последние 10 сообщений до новой реплики: это реплики 1–5.
    assert [item["content"] for item in last_call["history"]] == [
        "message 1",
        DEFAULT_CHAT_ANSWER,
        "message 2",
        DEFAULT_CHAT_ANSWER,
        "message 3",
        DEFAULT_CHAT_ANSWER,
        "message 4",
        DEFAULT_CHAT_ANSWER,
        "message 5",
        DEFAULT_CHAT_ANSWER,
    ]


async def test_trim_history_ignores_broken_entries() -> None:
    raw = [
        {"role": "system", "content": "ignore"},
        {"role": "user", "content": "  hi  "},
        {"role": "assistant"},
        "not a dict",
        {"role": "assistant", "content": "hello"},
        {"role": "user", "content": "   "},
    ]

    assert trim_history(raw) == [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello"},
    ]
    assert trim_history("broken") == []
    assert trim_history(raw, limit=1) == [{"role": "assistant", "content": "hello"}]


def test_append_exchange_keeps_only_last_messages() -> None:
    history: list[dict[str, str]] = []
    for number in range(HISTORY_LIMIT // 2):
        history = append_exchange(history, f"q{number}", f"a{number}")

    assert len(history) == HISTORY_LIMIT
    assert history[0] == {"role": "user", "content": "q0"}
    assert history[-1] == {"role": "assistant", "content": "a4"}


async def test_ai_error_keeps_chat_open_and_history_unchanged(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _create_user(session_factory)
    chat = FakeChat(USER_ID)
    state = make_state(USER_ID)
    await state.set_state(FreeChatStates.chatting)
    await state.set_data({HISTORY_KEY: []})
    ai = FakeAIClient(error=AITimeoutError("timeout"))

    await _send(session_factory, chat, state, ai, "Hello")

    assert chat.messages[-1] == t("common.ai_unavailable", "ru")
    assert await state.get_state() == FreeChatStates.chatting.state
    assert await _history(state) == []
    assert await _chat_activities(session_factory) == []


# --- 11.5 закрытие ---------------------------------------------------------


async def test_close_free_chat_clears_state_and_history(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _create_user(session_factory)
    chat = FakeChat(USER_ID)
    state = make_state(USER_ID)
    ai = FakeAIClient()
    await _open(session_factory, chat, state, ai)
    await _send(session_factory, chat, state, ai, "Hello")
    assert await _history(state) != []

    await _close(session_factory, chat, state, ai)

    assert await state.get_state() is None
    assert await state.get_data() == {}
    assert chat.messages[-1] == t("chat.closed", "ru")


async def test_close_without_chat_does_not_touch_other_mode(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _create_user(session_factory)
    chat = FakeChat(USER_ID)
    state = make_state(USER_ID)
    await state.set_state(QuizStates.answering)
    await state.set_data({"question_id": 1})

    await _close(session_factory, chat, state, FakeAIClient())

    assert await state.get_state() == QuizStates.answering.state
    assert (await state.get_data())["question_id"] == 1
    assert chat.messages[-1] == t("chat.not_active", "ru")


# --- 11.6 смена режима -----------------------------------------------------


async def test_other_command_closes_chat_first(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _create_user(session_factory)
    chat = FakeChat(USER_ID)
    state = make_state(USER_ID)
    ai = FakeAIClient()
    await _open(session_factory, chat, state, ai)
    await _send(session_factory, chat, state, ai, "Hello")

    middleware = FreeChatExitMiddleware()
    command = FakeMessage(chat)
    command.text = "/quiz"

    async def handler(event: Any, data: dict[str, Any]) -> str:
        return "quiz"

    assert await middleware(handler, command, {"state": state}) == "quiz"
    assert await state.get_state() is None
    assert await state.get_data() == {}

    # После закрытия команда другого режима работает сразу.
    await _dispatch(session_factory, quiz_command, FakeMessage(chat), state, ai)
    assert await state.get_state() == QuizStates.answering.state


async def test_plain_message_does_not_close_chat(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _create_user(session_factory)
    chat = FakeChat(USER_ID)
    state = make_state(USER_ID)
    await state.set_state(FreeChatStates.chatting)
    await state.set_data({HISTORY_KEY: []})

    middleware = FreeChatExitMiddleware()
    message = FakeMessage(chat)
    message.text = "how are you?"

    async def handler(event: Any, data: dict[str, Any]) -> str:
        return "ok"

    assert await middleware(handler, message, {"state": state}) == "ok"
    assert await state.get_state() == FreeChatStates.chatting.state


async def test_close_command_is_left_to_its_handler() -> None:
    chat = FakeChat(USER_ID)
    state = make_state(USER_ID)
    await state.set_state(FreeChatStates.chatting)
    await state.set_data({HISTORY_KEY: [{"role": "user", "content": "hi"}]})

    middleware = FreeChatExitMiddleware()
    message = FakeMessage(chat)
    message.text = "/close_free_chat"

    async def handler(event: Any, data: dict[str, Any]) -> str:
        return "closed"

    assert await middleware(handler, message, {"state": state}) == "closed"
    assert await state.get_state() == FreeChatStates.chatting.state


# --- 11.7 активность -------------------------------------------------------


async def test_chat_registers_one_activity_per_day(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _create_user(session_factory)
    chat = FakeChat(USER_ID)
    state = make_state(USER_ID)
    ai = FakeAIClient()
    await _open(session_factory, chat, state, ai)

    await _send(session_factory, chat, state, ai, "Hello")
    await _send(session_factory, chat, state, ai, "How are you?")
    await _send(session_factory, chat, state, ai, "Nice")

    activities = await _chat_activities(session_factory)
    assert len(activities) == 1
    assert activities[0].user_id == USER_ID

    async with session_factory() as session:
        streak = await session.get(Streak, USER_ID)
        assert streak is not None
        assert streak.current_streak == 1
        assert streak.best_streak == 1


async def test_chat_does_not_change_user_level(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _create_user(session_factory)
    chat = FakeChat(USER_ID)
    state = make_state(USER_ID)
    ai = FakeAIClient()
    await _open(session_factory, chat, state, ai)
    await _send(session_factory, chat, state, ai, "Hello")

    async with session_factory() as session:
        user = await UserRepo(session).get(USER_ID)
        assert user is not None
        assert user.level == "B1"


async def test_default_level_used_before_level_test(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _create_user(session_factory, level=None)
    chat = FakeChat(USER_ID)
    state = make_state(USER_ID)
    ai = FakeAIClient()
    await _open(session_factory, chat, state, ai)

    await _send(session_factory, chat, state, ai, "Hello")

    assert ai.calls_of("free_chat")[-1]["level"] == "A2"
