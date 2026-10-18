"""Тесты напоминаний и планировщика.

Ключевые проверки: нужный час в разных часовых поясах, лимит двух сообщений
в сутки, повторный запуск в тот же час без дублей, блокировка бота и
остановка рассылки после 7 дней молчания.
"""

import inspect
from datetime import date, datetime, time, timedelta, timezone
from typing import Any

from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.methods import SendMessage
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.config import Settings
from bot.keyboards import REMINDER_QUICK_CALLBACK, reminder_quick_kb
from bot.locales import t
from bot.middlewares.ai import AIClientMiddleware
from bot.middlewares.user import UserMiddleware
from bot.models import ActivityLog, Streak, User
from bot.repositories import StreakRepo, UserRepo
from bot.routers.reminders import quick_start_callback
from bot.scheduler import (
    CHECK_JOB_ID,
    _redis_jobstore,
    build_scheduler,
    check_streaks,
)
from bot.services.fake_ai_client import FakeAIClient
from bot.services.reminders import (
    MAX_PER_DAY,
    MAX_SILENT_DAYS,
    QUICK_START_WORDS,
    VARIANTS,
)
from tests.fakes import FakeCallbackQuery, FakeChat, FakeMessage, FakeUpdate

UTC_USER = 3001
SAM_USER = 3002


class FakeBot:
    """Бот, запоминающий отправленные сообщения и умеющий падать по команде."""

    def __init__(self) -> None:
        self.messages: list[dict[str, Any]] = []
        self.errors: list[Exception] = []

    async def send_message(
        self, chat_id: int, text: str, reply_markup: Any = None, **kwargs: Any
    ) -> None:
        if self.errors:
            raise self.errors.pop(0)
        self.messages.append({"chat_id": chat_id, "text": text, "reply_markup": reply_markup})


async def _create_user(
    session_factory: async_sessionmaker[AsyncSession],
    user_id: int,
    *,
    timezone_name: str,
    last_activity: date | None = None,
    streak: int = 0,
    best: int | None = None,
    created_on: date | None = None,
) -> None:
    async with session_factory() as session:
        async with session.begin():
            await UserRepo(session).create(user_id, native_language="ru", timezone=timezone_name)
            if created_on is not None:
                user = await UserRepo(session).get(user_id)
                assert user is not None
                user.created_at = datetime.combine(created_on, time.min, tzinfo=timezone.utc)
            if last_activity is not None:
                await StreakRepo(session).set_progress(
                    user_id,
                    current_streak=streak,
                    best_streak=best if best is not None else streak,
                    last_activity_date=last_activity,
                )


async def _user(session_factory: async_sessionmaker[AsyncSession], user_id: int) -> User:
    async with session_factory() as session:
        user = await UserRepo(session).get(user_id)
        assert user is not None
        return user


async def _streak(session_factory: async_sessionmaker[AsyncSession], user_id: int) -> Streak:
    async with session_factory() as session:
        streak = await StreakRepo(session).get(user_id)
        assert streak is not None
        return streak


async def _run(
    session_factory: async_sessionmaker[AsyncSession],
    bot: FakeBot,
    now: datetime,
    *,
    hour_offset: int = 0,
    sleeps: list[float] | None = None,
):
    async def fake_sleep(seconds: float) -> None:
        if sleeps is not None:
            sleeps.append(seconds)

    return await check_streaks(
        session_factory,
        bot,
        now=now,
        hour_offset=hour_offset,
        sleep=fake_sleep,
        pause=0,
    )


# --- 12.2 нужный час в разных часовых поясах -------------------------------


async def test_morning_goes_only_to_matching_timezone(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    yesterday = date(2026, 10, 17)
    await _create_user(
        session_factory, UTC_USER, timezone_name="UTC", last_activity=yesterday, streak=3
    )
    await _create_user(
        session_factory,
        SAM_USER,
        timezone_name="Asia/Samarkand",
        last_activity=yesterday,
        streak=3,
    )
    bot = FakeBot()

    # 04:00 UTC — это 09:00 в Самарканде, но ещё ночь по UTC.
    run = await _run(session_factory, bot, datetime(2026, 10, 18, 4, 0, tzinfo=timezone.utc))

    assert run.sent == 1
    assert [message["chat_id"] for message in bot.messages] == [SAM_USER]

    # 09:00 UTC — утро у UTC-пользователя; в Самарканде уже 14:00.
    run = await _run(session_factory, bot, datetime(2026, 10, 18, 9, 0, tzinfo=timezone.utc))
    assert run.sent == 1
    assert [message["chat_id"] for message in bot.messages] == [SAM_USER, UTC_USER]


async def test_hour_offset_shifts_reminder_slot(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """REMINDER_HOUR_OFFSET позволяет увидеть вечернее сообщение утром."""
    await _create_user(
        session_factory,
        UTC_USER,
        timezone_name="UTC",
        last_activity=date(2026, 10, 17),
        streak=4,
    )
    bot = FakeBot()

    # 09:00 + 11 часов = 20:00 — вечернее напоминание вместо утреннего.
    run = await _run(
        session_factory,
        bot,
        datetime(2026, 10, 18, 9, 0, tzinfo=timezone.utc),
        hour_offset=11,
    )

    assert run.sent == 1
    assert bot.messages[0]["text"] in {
        t(f"reminder.evening.{index}", "ru", days=4) for index in range(1, VARIANTS["evening"] + 1)
    }


async def test_no_reminder_outside_scheduled_hours(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _create_user(session_factory, UTC_USER, timezone_name="UTC")

    run = await _run(session_factory, FakeBot(), datetime(2026, 10, 18, 4, 0, tzinfo=timezone.utc))

    assert run.checked == 1
    assert run.sent == 0
    assert run.skipped == 1


async def test_morning_skipped_when_activity_today(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _create_user(
        session_factory,
        UTC_USER,
        timezone_name="UTC",
        last_activity=date(2026, 10, 18),
        streak=4,
    )
    bot = FakeBot()

    run = await _run(session_factory, bot, datetime(2026, 10, 18, 9, 0, tzinfo=timezone.utc))

    assert run.sent == 0
    assert bot.messages == []


# --- 12.3/12.4 утро и вечер -------------------------------------------------


async def test_evening_shows_current_streak(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _create_user(
        session_factory,
        SAM_USER,
        timezone_name="Asia/Samarkand",
        last_activity=date(2026, 10, 17),
        streak=6,
    )
    bot = FakeBot()

    run = await _run(session_factory, bot, datetime(2026, 10, 18, 15, 0, tzinfo=timezone.utc))

    assert run.sent == 1
    text = bot.messages[0]["text"]
    assert text in {
        t(f"reminder.evening.{index}", "ru", days=6) for index in range(1, VARIANTS["evening"] + 1)
    }
    assert bot.messages[0]["reply_markup"] is not None


async def test_evening_without_alive_streak_uses_cold_text(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _create_user(
        session_factory,
        UTC_USER,
        timezone_name="UTC",
        last_activity=date(2026, 10, 16),
        streak=6,
    )
    bot = FakeBot()

    run = await _run(session_factory, bot, datetime(2026, 10, 18, 20, 0, tzinfo=timezone.utc))

    assert run.sent == 1
    assert bot.messages[0]["text"] in {
        t(f"reminder.evening_cold.{index}", "ru")
        for index in range(1, VARIANTS["evening_cold"] + 1)
    }


# --- 12.5/12.6 пропуск и остановка -----------------------------------------


async def test_missed_day_reports_lost_streak_and_resets_it(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _create_user(
        session_factory,
        UTC_USER,
        timezone_name="UTC",
        last_activity=date(2026, 10, 16),
        streak=5,
    )
    bot = FakeBot()

    run = await _run(session_factory, bot, datetime(2026, 10, 18, 10, 0, tzinfo=timezone.utc))

    assert run.sent == 1
    assert bot.messages[0]["text"] in {
        t(f"reminder.missed.{index}", "ru", days=5) for index in range(1, VARIANTS["missed"] + 1)
    }
    streak = await _streak(session_factory, UTC_USER)
    assert streak.current_streak == 0
    assert streak.best_streak == 5


async def test_three_day_silence_sends_soft_reminder(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _create_user(
        session_factory,
        UTC_USER,
        timezone_name="UTC",
        last_activity=date(2026, 10, 15),
        streak=4,
    )
    bot = FakeBot()

    run = await _run(session_factory, bot, datetime(2026, 10, 18, 10, 0, tzinfo=timezone.utc))

    assert run.sent == 1
    assert bot.messages[0]["text"] in {
        t(f"reminder.missed_long.{index}", "ru", days=3)
        for index in range(1, VARIANTS["missed_long"] + 1)
    }


async def test_seven_day_silence_sends_last_reminder(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _create_user(
        session_factory,
        UTC_USER,
        timezone_name="UTC",
        last_activity=date(2026, 10, 11),
        streak=4,
    )
    bot = FakeBot()

    run = await _run(session_factory, bot, datetime(2026, 10, 18, 10, 0, tzinfo=timezone.utc))

    assert run.sent == 1
    assert bot.messages[0]["text"] in {
        t(f"reminder.missed_long.{index}", "ru", days=7)
        for index in range(1, VARIANTS["missed_long"] + 1)
    }


async def test_no_reminders_after_seven_silent_days(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    # 18 − 10 = 8 дней молчания: больше MAX_SILENT_DAYS.
    last_activity = date(2026, 10, 18) - timedelta(days=MAX_SILENT_DAYS + 1)
    await _create_user(
        session_factory,
        UTC_USER,
        timezone_name="UTC",
        last_activity=last_activity,
        streak=2,
    )
    bot = FakeBot()

    run = await _run(session_factory, bot, datetime(2026, 10, 18, 9, 0, tzinfo=timezone.utc))

    assert run.sent == 0
    assert bot.messages == []


async def test_user_who_never_studied_gets_reminders_first_week(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _create_user(
        session_factory, UTC_USER, timezone_name="UTC", created_on=date(2026, 10, 16)
    )

    run = await _run(session_factory, FakeBot(), datetime(2026, 10, 18, 9, 0, tzinfo=timezone.utc))

    assert run.sent == 1


# --- 12.7 лимит и идемпотентность ------------------------------------------


async def test_same_hour_rerun_sends_no_duplicates(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _create_user(
        session_factory,
        UTC_USER,
        timezone_name="UTC",
        last_activity=date(2026, 10, 17),
        streak=2,
    )
    bot = FakeBot()
    moment = datetime(2026, 10, 18, 9, 0, tzinfo=timezone.utc)

    first = await _run(session_factory, bot, moment)
    second = await _run(session_factory, bot, moment)

    assert (first.sent, second.sent) == (1, 0)
    assert len(bot.messages) == 1
    streak = await _streak(session_factory, UTC_USER)
    assert streak.reminders_count == 1


async def test_two_messages_per_day_and_no_third(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _create_user(
        session_factory,
        UTC_USER,
        timezone_name="UTC",
        last_activity=date(2026, 10, 17),
        streak=2,
    )
    bot = FakeBot()

    await _run(session_factory, bot, datetime(2026, 10, 18, 9, 0, tzinfo=timezone.utc))
    await _run(session_factory, bot, datetime(2026, 10, 18, 20, 0, tzinfo=timezone.utc))
    # Тот же вечер, запуск ещё раз: дубля быть не должно.
    third = await _run(session_factory, bot, datetime(2026, 10, 18, 20, 0, tzinfo=timezone.utc))

    assert len(bot.messages) == MAX_PER_DAY
    assert third.sent == 0

    streak = await _streak(session_factory, UTC_USER)
    assert streak.reminders_count == MAX_PER_DAY
    assert streak.reminders_date == date(2026, 10, 18)


async def test_counter_resets_on_next_day(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _create_user(session_factory, UTC_USER, timezone_name="UTC")
    bot = FakeBot()

    await _run(session_factory, bot, datetime(2026, 10, 18, 9, 0, tzinfo=timezone.utc))
    await _run(session_factory, bot, datetime(2026, 10, 19, 9, 0, tzinfo=timezone.utc))

    assert len(bot.messages) == 2
    streak = await _streak(session_factory, UTC_USER)
    assert streak.reminders_date == date(2026, 10, 19)
    assert streak.reminders_count == 1


# --- 12.8 блокировка и лимиты Telegram -------------------------------------


async def test_blocked_user_is_marked_inactive(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _create_user(
        session_factory,
        UTC_USER,
        timezone_name="UTC",
        last_activity=date(2026, 10, 17),
        streak=2,
    )
    bot = FakeBot()
    bot.errors.append(
        TelegramForbiddenError(
            SendMessage(chat_id=UTC_USER, text="x"),
            "Forbidden: bot was blocked by the user",
        )
    )

    run = await _run(session_factory, bot, datetime(2026, 10, 18, 9, 0, tzinfo=timezone.utc))

    assert run.blocked == 1
    assert run.sent == 0
    user = await _user(session_factory, UTC_USER)
    assert user.is_active is False

    # Повторный запуск больше не беспокоит пользователя.
    again = await _run(session_factory, bot, datetime(2026, 10, 18, 20, 0, tzinfo=timezone.utc))
    assert again.checked == 0
    assert again.sent == 0


async def test_retry_after_waits_and_resends(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _create_user(
        session_factory,
        UTC_USER,
        timezone_name="UTC",
        last_activity=date(2026, 10, 17),
        streak=2,
    )
    bot = FakeBot()
    bot.errors.append(
        TelegramRetryAfter(
            SendMessage(chat_id=UTC_USER, text="x"),
            "Too Many Requests: retry after 7",
            retry_after=7,
        )
    )
    sleeps: list[float] = []

    run = await _run(
        session_factory,
        bot,
        datetime(2026, 10, 18, 9, 0, tzinfo=timezone.utc),
        sleeps=sleeps,
    )

    assert 7 in sleeps
    assert run.sent == 1
    assert len(bot.messages) == 1
    streak = await _streak(session_factory, UTC_USER)
    assert streak.reminders_count == 1


# --- 12.9/12.10 тексты и быстрый старт -------------------------------------


def test_every_reminder_variant_exists_in_both_languages() -> None:
    for slot, count in VARIANTS.items():
        for index in range(1, count + 1):
            assert t(f"reminder.{slot}.{index}", "ru", days=3)
            assert t(f"reminder.{slot}.{index}", "en", days=3)


def test_quick_start_button_has_callback() -> None:
    markup = reminder_quick_kb("ru")

    button = markup.inline_keyboard[0][0]
    assert button.callback_data == REMINDER_QUICK_CALLBACK
    assert button.text == t("reminder.button", "ru")


def _state(user_id: int) -> FSMContext:
    return FSMContext(MemoryStorage(), StorageKey(bot_id=1, chat_id=user_id, user_id=user_id))


async def _dispatch_callback(
    session_factory: async_sessionmaker[AsyncSession],
    callback: Any,
    ai: Any,
) -> None:
    ai_middleware = AIClientMiddleware(client=ai)
    user_middleware = UserMiddleware()

    async def caller(event: Any, data: dict[str, Any]) -> Any:
        params = inspect.signature(quick_start_callback).parameters
        kwargs = {key: value for key, value in data.items() if key in params}
        return await quick_start_callback(event, **kwargs)

    async def on_handler(update: Any, data: dict[str, Any]) -> Any:
        return await caller(callback, data)

    async def on_user(update: Any, data: dict[str, Any]) -> Any:
        return await user_middleware(on_handler, update, data)

    async with session_factory() as session:
        async with session.begin():
            data = {
                "session": session,
                "state": _state(callback.from_user.id),
                "event_from_user": callback.from_user,
            }
            await ai_middleware(on_user, FakeUpdate(callback), data)


async def test_quick_start_sends_five_words_and_counts_activity(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _create_user(session_factory, UTC_USER, timezone_name="UTC")
    chat = FakeChat(UTC_USER)
    message = FakeMessage(chat)
    callback = FakeCallbackQuery(REMINDER_QUICK_CALLBACK, message)
    ai = FakeAIClient()

    await _dispatch_callback(session_factory, callback, ai)

    call = ai.calls_of("vocabulary")[-1]
    assert call["count"] == QUICK_START_WORDS
    assert chat.messages[-1].startswith(t("reminder.quick_title", "ru", count=QUICK_START_WORDS))
    assert "1. apple" in chat.messages[-1]

    async with session_factory() as session:
        rows = await session.scalars(select(ActivityLog).where(ActivityLog.user_id == UTC_USER))
        assert [row.kind for row in rows] == ["vocabulary"]


# --- 12.1 планировщик -------------------------------------------------------


def test_redis_jobstore_parses_url() -> None:
    """RedisJobStore собирается из URL вручную: redis-py 5 не знает `url`."""
    store = _redis_jobstore("redis://:secret@redis.local:6380/3")
    options = store.redis.connection_pool.connection_kwargs

    assert options["host"] == "redis.local"
    assert options["port"] == 6380
    assert options["db"] == 3
    assert options["password"] == "secret"


async def test_scheduler_registers_hourly_job(
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: Any,
) -> None:
    async def no_redis(url: str) -> bool:
        return False

    monkeypatch.setattr("bot.scheduler._redis_available", no_redis)
    settings = Settings(bot_token="123:test")
    scheduler = await build_scheduler(FakeBot(), settings)

    job = scheduler.get_job(CHECK_JOB_ID)
    assert job is not None
    fields = {field.name: str(field) for field in job.trigger.fields}
    assert fields["minute"] == "0"
    assert fields["hour"] == "*"
    # Задача должна переживать RedisJobStore: объект Bot в аргументы не попадает.
    assert job.func_ref == "bot.scheduler:run_hourly_check"
    assert job.args == ()
