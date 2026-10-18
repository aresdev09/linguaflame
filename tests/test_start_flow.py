"""Тесты онбординга /start."""

import inspect
from typing import Any

from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.locales import t
from bot.middlewares.user import UserMiddleware
from bot.models import User
from bot.repositories import UserRepo
from bot.routers.start import choose_language, choose_timezone, start_command
from bot.states import OnboardingStates

USER_ID = 555


class FakeTelegramUser:
    def __init__(self, user_id: int, first_name: str, username: str | None) -> None:
        self.id = user_id
        self.first_name = first_name
        self.username = username


class FakeMessage:
    def __init__(self, first_name: str = "Аня", username: str | None = None) -> None:
        self.from_user = FakeTelegramUser(USER_ID, first_name, username)
        self.answers: list[str] = []
        self.markups: list[Any] = []

    async def answer(self, text: str, **kwargs: Any) -> None:
        self.answers.append(text)
        self.markups.append(kwargs.get("reply_markup"))


class FakeCallbackQuery:
    def __init__(self, data: str, message: FakeMessage) -> None:
        self.data = data
        self.message = message
        self.from_user = message.from_user
        self.answers: list[str] = []

    async def answer(self, text: str = "", **kwargs: Any) -> None:
        self.answers.append(text)


def _state() -> FSMContext:
    key = StorageKey(bot_id=1, chat_id=USER_ID, user_id=USER_ID)
    return FSMContext(MemoryStorage(), key)


class FakeUpdate:
    """Апдейт в форме aiogram: middleware видят Update, хендлеры — вложенное событие."""

    def __init__(self, event: Any, update_id: int = 1) -> None:
        self.event = event
        self.update_id = update_id


async def _dispatch(
    session_factory: async_sessionmaker[AsyncSession],
    handler: Any,
    event: Any,
    state: FSMContext,
) -> Any:
    """Прогоняет апдейт через UserMiddleware и вызывает хендлер как aiogram."""
    middleware = UserMiddleware()
    caller = _as_aiogram_caller(handler)

    async def on_update(update: Any, data: dict[str, Any]) -> Any:
        return await caller(event, data)

    async with session_factory() as session:
        async with session.begin():
            data = {
                "session": session,
                "state": state,
                "event_from_user": event.from_user,
            }
            return await middleware(on_update, FakeUpdate(event), data)


def _as_aiogram_caller(handler: Any) -> Any:
    """Как aiogram: в хендлер уходят только параметры из его сигнатуры."""

    async def caller(event: Any, data: dict[str, Any]) -> Any:
        params = inspect.signature(handler).parameters
        kwargs = {key: value for key, value in data.items() if key in params}
        return await handler(event, **kwargs)

    return caller


async def test_new_user_start_creates_user_and_offers_languages(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    message = FakeMessage()
    state = _state()

    await _dispatch(session_factory, start_command, message, state)

    async with session_factory() as session:
        user = await UserRepo(session).get(USER_ID)
        assert user is not None
        assert user.username is None
        assert user.timezone == "UTC"
        assert user.native_language == "en"

    assert await state.get_state() == OnboardingStates.choose_language.state
    assert message.answers[0] == t("start.greeting", "ru", name="Аня")
    assert message.answers[1] == t("start.choose_language", "ru")
    assert message.markups[1] is not None


async def test_choose_language_saves_profile_and_asks_timezone(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    message = FakeMessage()
    state = _state()
    await _dispatch(session_factory, start_command, message, state)

    callback = FakeCallbackQuery("lang:ru", message)
    await _dispatch(session_factory, choose_language, callback, state)

    assert await state.get_state() == OnboardingStates.choose_timezone.state
    assert callback.answers == [""]

    async with session_factory() as session:
        user = await UserRepo(session).get(USER_ID)
        assert user is not None
        assert user.native_language == "ru"

    assert message.answers[-1] == t("start.choose_timezone", "ru")


async def test_choose_language_rejects_unknown_language(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    message = FakeMessage()
    state = _state()
    await _dispatch(session_factory, start_command, message, state)

    callback = FakeCallbackQuery("lang:xx", message)
    await _dispatch(session_factory, choose_language, callback, state)

    assert callback.answers == [t("common.language_not_supported", "en")]
    assert await state.get_state() == OnboardingStates.choose_language.state


async def test_repeated_start_keeps_single_user_row(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    state = _state()
    first = FakeMessage()
    await _dispatch(session_factory, start_command, first, state)

    second = FakeMessage()
    await _dispatch(session_factory, start_command, second, state)

    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(User)) == 1

    assert await state.get_state() is None
    assert second.answers[0] == t(
        "start.already_configured",
        "en",
        name="Аня",
        language="English",
        timezone="UTC",
    )


async def test_onboarding_saves_language_and_timezone(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    message = FakeMessage()
    state = _state()
    await _dispatch(session_factory, start_command, message, state)

    await _dispatch(
        session_factory, choose_language, FakeCallbackQuery("lang:ru", message), state
    )
    callback = FakeCallbackQuery("tz:Asia/Samarkand", message)
    await _dispatch(session_factory, choose_timezone, callback, state)

    assert await state.get_state() is None
    assert callback.answers == [""]
    assert message.answers[-2] == t(
        "start.timezone_saved", "ru", timezone="Asia/Samarkand"
    )

    async with session_factory() as session:
        user = await UserRepo(session).get(USER_ID)
        assert user is not None
        assert user.native_language == "ru"
        assert user.timezone == "Asia/Samarkand"


async def test_choose_timezone_rejects_unknown_timezone(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    message = FakeMessage()
    state = _state()
    await _dispatch(session_factory, start_command, message, state)
    await _dispatch(
        session_factory, choose_language, FakeCallbackQuery("lang:ru", message), state
    )

    callback = FakeCallbackQuery("tz:Mars/Olympus", message)
    await _dispatch(session_factory, choose_timezone, callback, state)

    assert callback.answers == [t("common.timezone_invalid", "ru")]
    assert await state.get_state() == OnboardingStates.choose_timezone.state

    async with session_factory() as session:
        user = await UserRepo(session).get(USER_ID)
        assert user is not None
        assert user.timezone == "UTC"