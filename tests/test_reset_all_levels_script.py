"""Тесты массового сброса уровней (`scripts.reset_all_levels`)."""

from datetime import datetime
from typing import Any

from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
from aiogram.methods import SendMessage
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.locales import t
from bot.repositories import UserRepo
from scripts import reset_all_levels as script


class FakeBot:
    """Бот, запоминающий сообщения и умеющий падать по команде для chat_id."""

    def __init__(self) -> None:
        self.messages: list[dict[str, Any]] = []
        self.errors: dict[int, Exception] = {}

    async def send_message(self, chat_id: int, text: str, **kwargs: Any) -> None:
        error = self.errors.pop(chat_id, None)
        if error is not None:
            raise error
        self.messages.append({"chat_id": chat_id, "text": text})


async def _no_sleep(_seconds: float) -> None:
    """Тестовая пауза: рассылка не тормозит тесты."""


async def _create_user(
    session_factory: async_sessionmaker[AsyncSession],
    user_id: int,
    *,
    level: str | None,
    lang: str = "ru",
) -> None:
    async with session_factory() as session:
        async with session.begin():
            repo = UserRepo(session)
            await repo.get_or_create(user_id, native_language=lang)
            if level is not None:
                await repo.set_level(user_id, level, datetime.now())


async def test_resets_levels_and_sends_notice(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _create_user(session_factory, 1, level="C2", lang="ru")
    await _create_user(session_factory, 2, level="B1", lang="en")
    await _create_user(session_factory, 3, level=None)
    bot = FakeBot()

    run = await script.reset_all_levels(session_factory, bot, sleep=_no_sleep)

    assert run == script.ResetRun(total=2, reset=2, sent=2, blocked=0, failed=0)
    texts = {message["chat_id"]: message["text"] for message in bot.messages}
    assert texts == {
        1: t("level.reset_notice", "ru"),
        2: t("level.reset_notice", "en"),
    }
    assert "/level_detector" in texts[1]
    async with session_factory() as session:
        repo = UserRepo(session)
        first = await repo.get(1)
        assert first is not None
        assert first.level is None
        assert first.level_tested_at is None
        assert (await repo.get(2)).level is None
        assert (await repo.get(3)).level is None


async def test_dry_run_changes_nothing(
    session_factory: async_sessionmaker[AsyncSession],
    capsys: Any,
) -> None:
    await _create_user(session_factory, 1, level="C2")
    bot = FakeBot()

    run = await script.reset_all_levels(session_factory, bot, dry_run=True, sleep=_no_sleep)

    assert run == script.ResetRun(total=1)
    assert bot.messages == []
    async with session_factory() as session:
        assert (await UserRepo(session).get(1)).level == "C2"
    printed = capsys.readouterr().out
    assert "1" in printed
    assert "C2" in printed


async def test_blocked_user_is_deactivated_and_others_notified(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _create_user(session_factory, 1, level="C2")
    await _create_user(session_factory, 2, level="B1")
    bot = FakeBot()
    bot.errors[1] = TelegramForbiddenError(
        SendMessage(chat_id=1, text="x"), "Forbidden: bot was blocked by the user"
    )

    run = await script.reset_all_levels(session_factory, bot, sleep=_no_sleep)

    assert run == script.ResetRun(total=2, reset=2, sent=1, blocked=1, failed=0)
    assert [message["chat_id"] for message in bot.messages] == [2]
    async with session_factory() as session:
        repo = UserRepo(session)
        assert (await repo.get(1)).is_active is False
        assert (await repo.get(2)).is_active is True


async def test_send_failure_counts_and_level_still_reset(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _create_user(session_factory, 1, level="C2")
    bot = FakeBot()
    bot.errors[1] = RuntimeError("boom")

    run = await script.reset_all_levels(session_factory, bot, sleep=_no_sleep)

    assert run == script.ResetRun(total=1, reset=1, sent=0, blocked=0, failed=1)
    async with session_factory() as session:
        assert (await UserRepo(session).get(1)).level is None


async def test_retry_after_resends_notice(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _create_user(session_factory, 1, level="C2")
    bot = FakeBot()
    bot.errors[1] = TelegramRetryAfter(
        SendMessage(chat_id=1, text="x"), "Too Many Requests", retry_after=1
    )

    run = await script.reset_all_levels(session_factory, bot, sleep=_no_sleep)

    assert run == script.ResetRun(total=1, reset=1, sent=1, blocked=0, failed=0)
    assert [message["chat_id"] for message in bot.messages] == [1]
