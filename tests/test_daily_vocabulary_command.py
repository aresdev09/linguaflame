"""Тесты команды /daily_vocabulary."""

import inspect
from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.locales import t
from bot.middlewares.ai import AIClientMiddleware
from bot.middlewares.user import UserMiddleware
from bot.models import ActivityLog, VocabularySet
from bot.repositories import StreakRepo, UserRepo
from bot.routers.daily_vocabulary import daily_vocabulary_command
from bot.services.ai_errors import AIRequestError
from bot.services.ai_schemas import VocabularyResponse, Word
from bot.services.fake_ai_client import FakeAIClient

USER_ID = 902
SAMARKAND = ZoneInfo("Asia/Samarkand")


class FakeTelegramUser:
    def __init__(self, user_id: int, first_name: str = "Аня") -> None:
        self.id = user_id
        self.first_name = first_name
        self.username = None


class FakeSentMessage:
    """Сообщение, которое можно отредактировать (как в Telegram)."""

    def __init__(self, chat: "FakeMessage", index: int) -> None:
        self._chat = chat
        self._index = index

    async def edit_text(self, text: str, **kwargs: Any) -> None:
        self._chat.answers[self._index] = text


class FakeMessage:
    def __init__(self) -> None:
        self.from_user = FakeTelegramUser(USER_ID)
        self.answers: list[str] = []

    async def answer(self, text: str, **kwargs: Any) -> FakeSentMessage:
        self.answers.append(text)
        return FakeSentMessage(self, len(self.answers) - 1)


class FakeUpdate:
    """Апдейт в форме aiogram: middleware видит Update, хендлер — вложенное событие."""

    def __init__(self, event: Any, update_id: int = 1) -> None:
        self.event = event
        self.update_id = update_id


def _as_aiogram_caller(handler: Any) -> Any:
    """Как aiogram: в хендлер уходят только параметры из его сигнатуры."""

    async def caller(event: Any, data: dict[str, Any]) -> Any:
        params = inspect.signature(handler).parameters
        kwargs = {key: value for key, value in data.items() if key in params}
        return await handler(event, **kwargs)

    return caller


async def _dispatch(
    session_factory: async_sessionmaker[AsyncSession],
    message: FakeMessage,
    ai: FakeAIClient,
) -> None:
    ai_middleware = AIClientMiddleware(client=ai)
    user_middleware = UserMiddleware()
    caller = _as_aiogram_caller(daily_vocabulary_command)

    async def on_handler(update: Any, data: dict[str, Any]) -> Any:
        return await caller(message, data)

    async def on_ai(update: Any, data: dict[str, Any]) -> Any:
        return await user_middleware(on_handler, update, data)

    async with session_factory() as session:
        async with session.begin():
            data = {"session": session, "event_from_user": message.from_user}
            await ai_middleware(on_ai, FakeUpdate(message), data)


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
                timezone="Asia/Samarkand",
            )
            if level is not None:
                await repo.set_level(USER_ID, level, datetime.now(timezone.utc))


class _LoadingAwareAIClient(FakeAIClient):
    """Запоминает, что бот успел показать к моменту запроса к ИИ."""

    def __init__(self, message: FakeMessage) -> None:
        super().__init__()
        self.message = message
        self.answers_at_call: list[list[str]] = []

    async def generate_vocabulary(
        self,
        level: str,
        lang: str,
        *,
        count: int = 20,
        exclude_words=(),
    ) -> VocabularyResponse:
        self.answers_at_call.append(list(self.message.answers))
        return await super().generate_vocabulary(
            level, lang, count=count, exclude_words=exclude_words
        )


def _item_lines(text: str) -> list[str]:
    return [line for line in text.splitlines() if line and line[0].isdigit()]


async def test_command_sends_twenty_words_and_registers_activity(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _create_user(session_factory, level="B1")
    ai = FakeAIClient()
    message = FakeMessage()

    await _dispatch(session_factory, message, ai)

    assert len(message.answers) == 1
    text = message.answers[0]
    assert text.startswith(t("vocabulary.title", "ru", level="B1"))
    assert len(_item_lines(text)) == 20
    assert t("vocabulary.default_level", "ru", level="A2") not in text

    first = ai.vocabulary.words[0]
    assert (
        t(
            "vocabulary.item",
            "ru",
            index=1,
            word=first.word,
            transcription=f"/{first.word}/",
            translation=first.translation,
        )
        in text
    )

    async with session_factory() as session:
        assert len(list(await session.scalars(select(VocabularySet)))) == 1
        assert list(await session.scalars(select(ActivityLog.kind))) == ["vocabulary"]
        streak = await StreakRepo(session).get(USER_ID)
        assert streak is not None
        assert streak.current_streak == 1


async def test_loading_message_is_sent_before_ai_request(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _create_user(session_factory)
    message = FakeMessage()
    ai = _LoadingAwareAIClient(message)

    await _dispatch(session_factory, message, ai)

    assert ai.answers_at_call == [[t("vocabulary.loading", "ru")]]
    assert t("vocabulary.loading", "ru") not in message.answers[0]
    assert len(_item_lines(message.answers[0])) == 20


async def test_repeated_command_returns_saved_set_without_ai(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _create_user(session_factory)
    ai = FakeAIClient()
    first_message = FakeMessage()
    second_message = FakeMessage()

    await _dispatch(session_factory, first_message, ai)
    await _dispatch(session_factory, second_message, ai)

    assert len(ai.calls_of("vocabulary")) == 1
    assert t("vocabulary.reused", "ru") in second_message.answers[0]
    assert t("vocabulary.reused", "ru") not in first_message.answers[0]
    assert _item_lines(second_message.answers[0]) == _item_lines(first_message.answers[0])

    async with session_factory() as session:
        assert len(list(await session.scalars(select(VocabularySet)))) == 1
        assert len(list(await session.scalars(select(ActivityLog)))) == 2
        streak = await StreakRepo(session).get(USER_ID)
        assert streak.current_streak == 1


async def test_default_level_is_reported_with_hint(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _create_user(session_factory, level=None)
    ai = FakeAIClient()
    message = FakeMessage()

    await _dispatch(session_factory, message, ai)

    assert t("vocabulary.default_level", "ru", level="A2") in message.answers[0]


async def test_long_list_is_split_into_two_messages(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _create_user(session_factory)
    long_words = VocabularyResponse(
        words=[
            Word(
                word=f"word{index}",
                transcription=f"/w{index}/",
                translation="очень длинный перевод слова " * 12,
            )
            for index in range(1, 21)
        ]
    )
    ai = FakeAIClient(vocabulary=long_words)
    message = FakeMessage()

    await _dispatch(session_factory, message, ai)

    assert len(message.answers) == 2
    assert all(len(chunk) <= 4096 for chunk in message.answers)
    assert sum(len(_item_lines(chunk)) for chunk in message.answers) == 20


async def test_ai_error_shows_localized_message(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _create_user(session_factory)
    ai = FakeAIClient(error=AIRequestError("ИИ недоступен"))
    message = FakeMessage()

    await _dispatch(session_factory, message, ai)

    assert message.answers == [t("common.ai_unavailable", "ru")]

    async with session_factory() as session:
        assert list(await session.scalars(select(VocabularySet))) == []
        assert list(await session.scalars(select(ActivityLog))) == []
