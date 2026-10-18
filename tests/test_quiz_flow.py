"""Сценарии команды /quiz: верный/неверный ответ, повторы и завершение."""

import inspect
from datetime import datetime, timezone
from typing import Any

from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.keyboards import QUIZ_FINISH_CALLBACK
from bot.locales import t
from bot.middlewares.ai import AIClientMiddleware
from bot.middlewares.user import UserMiddleware
from bot.models import ActivityLog
from bot.repositories import QuestionRepo, StreakRepo, UserRepo
from bot.routers.quiz import quiz_callback, quiz_command
from bot.services.fake_ai_client import FakeAIClient
from bot.states import QuizStates

USER_ID = 702


class FakeTelegramUser:
    def __init__(self, user_id: int = USER_ID) -> None:
        self.id = user_id
        self.first_name = "Аня"
        self.username = None


class FakeChat:
    """Переписка: все сообщения бота подряд и их клавиатуры."""

    def __init__(self) -> None:
        self.user = FakeTelegramUser()
        self.messages: list[str] = []
        self.markups: list[Any] = []


class FakeMessage:
    def __init__(self, chat: FakeChat, index: int | None = None) -> None:
        self.chat = chat
        self.index = index
        self.from_user = chat.user

    async def answer(self, text: str, **kwargs: Any) -> "FakeMessage":
        self.chat.messages.append(text)
        self.chat.markups.append(kwargs.get("reply_markup"))
        return FakeMessage(self.chat, len(self.chat.messages) - 1)

    async def edit_text(self, text: str, **kwargs: Any) -> None:
        assert self.index is not None, "редактировать можно только отправленное сообщение"
        self.chat.messages[self.index] = text
        if "reply_markup" in kwargs:
            self.chat.markups[self.index] = kwargs["reply_markup"]


class FakeCallbackQuery:
    def __init__(self, data: str, message: FakeMessage) -> None:
        self.data = data
        self.message = message
        self.from_user = message.from_user
        self.answers: list[str] = []

    async def answer(self, text: str = "", **kwargs: Any) -> None:
        self.answers.append(text)


class FakeUpdate:
    def __init__(self, event: Any, update_id: int = 1) -> None:
        self.event = event
        self.update_id = update_id


def _state() -> FSMContext:
    key = StorageKey(bot_id=1, chat_id=USER_ID, user_id=USER_ID)
    return FSMContext(MemoryStorage(), key)


def _as_aiogram_caller(handler: Any) -> Any:
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
    ai: FakeAIClient,
) -> None:
    ai_middleware = AIClientMiddleware(client=ai)
    user_middleware = UserMiddleware()
    caller = _as_aiogram_caller(handler)

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
            await repo.create(USER_ID, native_language=native_language)
            if level is not None:
                await repo.set_level(USER_ID, level, datetime.now(timezone.utc))


async def _seed_question(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    text: str,
    correct: str = "A",
    explanation: str = "Пояснение",
) -> int:
    async with session_factory() as session:
        async with session.begin():
            question = await QuestionRepo(session).create(
                kind="grammar",
                level="B1",
                text=text,
                options={"A": "am", "B": "is", "C": "are"},
                correct_option=correct,
                explanation=explanation,
            )
            return question.id


async def _start(
    session_factory: async_sessionmaker[AsyncSession],
    chat: FakeChat,
    state: FSMContext,
    ai: FakeAIClient,
) -> FakeMessage:
    await _dispatch(session_factory, quiz_command, FakeMessage(chat), state, ai)
    return FakeMessage(chat, len(chat.messages) - 1)


def _callbacks(markup: Any) -> list[str]:
    return [
        button.callback_data
        for row in markup.inline_keyboard
        for button in row
    ]


def _question_text(text: str, number: int = 1) -> str:
    return t("quiz.question", "ru", number=number, text=text)


async def test_correct_answer_shows_feedback_then_next_question(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _create_user(session_factory)
    first_id = await _seed_question(
        session_factory, text="I ___ a student.", explanation="С I — am."
    )
    second_id = await _seed_question(
        session_factory, text="She ___ a doctor.", correct="B"
    )
    chat = FakeChat()
    state = _state()
    ai = FakeAIClient()

    question_message = await _start(session_factory, chat, state, ai)

    assert chat.messages[0] == _question_text("I ___ a student.")
    assert await state.get_state() == QuizStates.answering.state
    callbacks = _callbacks(chat.markups[0])
    assert f"quiz:{first_id}:A" in callbacks
    assert f"quiz:{first_id}:B" in callbacks
    assert QUIZ_FINISH_CALLBACK in callbacks

    callback = FakeCallbackQuery(f"quiz:{first_id}:A", question_message)
    await _dispatch(session_factory, quiz_callback, callback, state, ai)

    assert callback.answers == [""]  # callback.answer() вызван ровно один раз
    feedback = chat.messages[0]
    assert feedback.startswith(t("quiz.correct", "ru"))
    assert t("quiz.correct_answer", "ru", option="A", answer="am") in feedback
    assert "С I — am." in feedback
    assert chat.markups[0].inline_keyboard == []
    assert chat.messages[1] == _question_text("She ___ a doctor.", number=2)

    data = await state.get_data()
    assert data["question_id"] == second_id
    assert data["correct_count"] == 1
    assert data["answered_count"] == 1
    assert data["answered"] is False
    assert data["used_ids"] == [first_id, second_id]

    async with session_factory() as session:
        assert list(await session.scalars(select(ActivityLog.kind))) == ["quiz"]
        streak = await StreakRepo(session).get(USER_ID)
        assert streak is not None
        assert streak.current_streak == 1


async def test_double_click_is_ignored_and_callback_still_answered(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _create_user(session_factory)
    first_id = await _seed_question(session_factory, text="I ___ a student.")
    await _seed_question(session_factory, text="She ___ a doctor.", correct="B")
    chat = FakeChat()
    state = _state()
    ai = FakeAIClient()

    question_message = await _start(session_factory, chat, state, ai)
    first = FakeCallbackQuery(f"quiz:{first_id}:A", question_message)
    await _dispatch(session_factory, quiz_callback, first, state, ai)

    repeated = FakeCallbackQuery(f"quiz:{first_id}:A", question_message)
    await _dispatch(session_factory, quiz_callback, repeated, state, ai)

    assert repeated.answers == [t("quiz.already_answered", "ru")]
    data = await state.get_data()
    assert data["correct_count"] == 1
    assert data["answered_count"] == 1

    async with session_factory() as session:
        assert list(await session.scalars(select(ActivityLog.kind))) == ["quiz"]


async def test_wrong_answer_shows_correct_option_and_generates_next(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _create_user(session_factory)
    first_id = await _seed_question(
        session_factory,
        text="She ___ a doctor.",
        explanation="С she — is.",
    )
    chat = FakeChat()
    state = _state()
    ai = FakeAIClient()

    question_message = await _start(session_factory, chat, state, ai)
    callback = FakeCallbackQuery(f"quiz:{first_id}:B", question_message)
    await _dispatch(session_factory, quiz_callback, callback, state, ai)

    feedback = chat.messages[0]
    assert feedback.startswith(t("quiz.wrong", "ru"))
    assert t("quiz.correct_answer", "ru", option="A", answer="am") in feedback
    assert "С she — is." in feedback

    # Банк исчерпан: следующий вопрос сгенерирован и сохранён.
    assert chat.messages[1] == _question_text(ai.quiz.question, number=2)
    assert len(ai.calls_of("quiz")) == 1

    data = await state.get_data()
    assert data["correct_count"] == 0
    assert data["answered_count"] == 1
    assert data["answered"] is False

    async with session_factory() as session:
        assert len(list(await session.scalars(select(ActivityLog)))) == 1


async def test_finish_shows_score_and_closes_session(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _create_user(session_factory)
    first_id = await _seed_question(session_factory, text="Первый вопрос")
    second_id = await _seed_question(session_factory, text="Второй вопрос")
    third_id = await _seed_question(session_factory, text="Третий вопрос")
    chat = FakeChat()
    state = _state()
    ai = FakeAIClient()

    first_message = await _start(session_factory, chat, state, ai)
    await _dispatch(
        session_factory,
        quiz_callback,
        FakeCallbackQuery(f"quiz:{first_id}:A", first_message),
        state,
        ai,
    )
    second_message = FakeMessage(chat, 1)
    await _dispatch(
        session_factory,
        quiz_callback,
        FakeCallbackQuery(f"quiz:{second_id}:B", second_message),
        state,
        ai,
    )

    data = await state.get_data()
    assert data["used_ids"] == [first_id, second_id, third_id]  # без повторов
    assert data["correct_count"] == 1
    assert data["answered_count"] == 2

    finish = FakeCallbackQuery(QUIZ_FINISH_CALLBACK, FakeMessage(chat, 2))
    await _dispatch(session_factory, quiz_callback, finish, state, ai)

    assert finish.answers == [""]
    assert await state.get_state() is None
    assert chat.messages[2] == t("quiz.result", "ru", correct=1, total=2)
    assert chat.markups[2].inline_keyboard == []
    assert ai.calls == []  # все вопросы взяты из банка

    async with session_factory() as session:
        assert len(list(await session.scalars(select(ActivityLog)))) == 2
        streak = await StreakRepo(session).get(USER_ID)
        assert streak.current_streak == 1

    # Нажатие после завершения не считается и всё равно получает answer().
    stale = FakeCallbackQuery(QUIZ_FINISH_CALLBACK, FakeMessage(chat, 2))
    await _dispatch(session_factory, quiz_callback, stale, state, ai)
    assert stale.answers == [t("quiz.not_active", "ru")]
    assert chat.messages[2] == t("quiz.result", "ru", correct=1, total=2)


async def test_finish_without_answers(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _create_user(session_factory)
    await _seed_question(session_factory, text="Первый вопрос")
    chat = FakeChat()
    state = _state()
    ai = FakeAIClient()

    question_message = await _start(session_factory, chat, state, ai)
    finish = FakeCallbackQuery(QUIZ_FINISH_CALLBACK, question_message)
    await _dispatch(session_factory, quiz_callback, finish, state, ai)

    assert finish.answers == [""]
    assert await state.get_state() is None
    assert chat.messages[0] == t("quiz.result_empty", "ru")

    async with session_factory() as session:
        assert list(await session.scalars(select(ActivityLog))) == []


async def test_invalid_callback_is_answered_without_scoring(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _create_user(session_factory)
    await _seed_question(session_factory, text="Первый вопрос")
    chat = FakeChat()
    state = _state()
    ai = FakeAIClient()

    question_message = await _start(session_factory, chat, state, ai)
    callback = FakeCallbackQuery("quiz:oops:A", question_message)
    await _dispatch(session_factory, quiz_callback, callback, state, ai)

    assert callback.answers == [t("quiz.invalid_option", "ru")]
    data = await state.get_data()
    assert data["answered_count"] == 0
    assert data["answered"] is False
