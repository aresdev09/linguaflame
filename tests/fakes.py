"""Общие подделки Telegram-событий для сценарных тестов роутеров."""

import inspect
from typing import Any

from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.middlewares.user import UserMiddleware


class FakeTelegramUser:
    """Минимальный Telegram-пользователь для middleware."""

    def __init__(self, user_id: int, first_name: str = "Аня") -> None:
        self.id = user_id
        self.first_name = first_name
        self.username = None


class FakeChat:
    """Переписка: все сообщения бота подряд и их клавиатуры."""

    def __init__(self, user_id: int) -> None:
        self.user = FakeTelegramUser(user_id)
        self.messages: list[str] = []
        self.markups: list[Any] = []
        # Настоящий Message в aiogram привязан к боту, у подделки бота нет:
        # хендлеры, которым нужен chat action, проверяют message.bot на None.
        self.bot = None


class FakeMessage:
    """Сообщение, умеющее отвечать и редактироваться."""

    def __init__(self, chat: FakeChat, index: int | None = None) -> None:
        self.chat = chat
        self.index = index
        self.from_user = chat.user
        self.bot = chat.bot

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
    """Callback-запрос с записью всех ответов `callback.answer()`."""

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


def make_state(user_id: int) -> FSMContext:
    """Свежий FSMContext (в каждом тесте своё хранилище)."""
    key = StorageKey(bot_id=1, chat_id=user_id, user_id=user_id)
    return FSMContext(MemoryStorage(), key)


def as_aiogram_caller(handler: Any) -> Any:
    """Вызывает хендлер напрямую, передавая только известные ему аргументы."""

    async def caller(event: Any, data: dict[str, Any]) -> Any:
        params = inspect.signature(handler).parameters
        kwargs = {key: value for key, value in data.items() if key in params}
        return await handler(event, **kwargs)

    return caller


async def dispatch(
    session_factory: async_sessionmaker[AsyncSession],
    handler: Any,
    event: Any,
    state: FSMContext,
) -> None:
    """Прогоняет событие через UserMiddleware в транзакции, как это делает бот."""
    user_middleware = UserMiddleware()
    caller = as_aiogram_caller(handler)

    async def on_handler(update: Any, data: dict[str, Any]) -> Any:
        return await caller(event, data)

    async with session_factory() as session:
        async with session.begin():
            data = {
                "session": session,
                "state": state,
                "event_from_user": event.from_user,
            }
            await user_middleware(on_handler, FakeUpdate(event), data)


def callbacks(markup: Any) -> list[str]:
    """Все callback_data кнопок клавиатуры."""
    return [
        button.callback_data
        for row in markup.inline_keyboard
        for button in row
    ]
