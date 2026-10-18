"""Тесты сервиса слов дня."""

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.models import ActivityLog, Streak, VocabularySet
from bot.repositories import StreakRepo, UserRepo, VocabularyRepo
from bot.services.ai_errors import AIRequestError, AIResponseError
from bot.services.ai_schemas import VocabularyResponse, Word
from bot.services.fake_ai_client import FakeAIClient
from bot.services.vocabulary import get_daily_vocabulary

USER_ID = 901
SAMARKAND = ZoneInfo("Asia/Samarkand")
NOW = datetime(2026, 10, 18, 12, 0, tzinfo=SAMARKAND)


async def _create_user(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    level: str | None = "B1",
    native_language: str = "ru",
    timezone_name: str = "Asia/Samarkand",
) -> None:
    async with session_factory() as session:
        async with session.begin():
            repo = UserRepo(session)
            await repo.create(
                USER_ID,
                native_language=native_language,
                timezone=timezone_name,
            )
            if level is not None:
                await repo.set_level(USER_ID, level, datetime.now(timezone.utc))


async def _get(
    session_factory: async_sessionmaker[AsyncSession],
    ai: FakeAIClient,
    now: datetime = NOW,
):
    async with session_factory() as session:
        async with session.begin():
            return await get_daily_vocabulary(session, USER_ID, ai, now=now)


def _words(*names: str) -> VocabularyResponse:
    return VocabularyResponse(
        words=[
            Word(
                word=name,
                transcription=f"/{name}/",
                translation=f"перевод {name}",
            )
            for name in names
        ]
    )


class _SequenceAIClient(FakeAIClient):
    """Отдаёт наборы слов по очереди — для проверки добора до 20."""

    def __init__(self, responses: list[VocabularyResponse]) -> None:
        super().__init__()
        self._responses = list(responses)

    async def generate_vocabulary(
        self,
        level: str,
        lang: str,
        *,
        count: int = 20,
        exclude_words=(),
    ) -> VocabularyResponse:
        self.calls.append(
            {
                "task": "vocabulary",
                "level": level,
                "lang": lang,
                "count": count,
                "exclude_words": list(exclude_words),
            }
        )
        return self._responses.pop(0)


class _SmallSetAIClient(FakeAIClient):
    """Всегда отдаёт два слова — сервис должен сдаться после повторов."""

    def __init__(self) -> None:
        super().__init__()
        self.requested_counts: list[int] = []

    async def generate_vocabulary(
        self,
        level: str,
        lang: str,
        *,
        count: int = 20,
        exclude_words=(),
    ) -> VocabularyResponse:
        self.requested_counts.append(count)
        return _words("one", "two")


async def test_first_request_generates_and_saves_twenty_words(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _create_user(session_factory, level="B1")
    ai = FakeAIClient()

    daily = await _get(session_factory, ai)

    assert len(daily.words) == 20
    assert daily.reused is False
    assert daily.level == "B1"
    assert daily.level_default is False
    assert all(word.word and word.transcription and word.translation for word in daily.words)

    calls = ai.calls_of("vocabulary")
    assert len(calls) == 1
    assert calls[0]["count"] == 20
    assert calls[0]["level"] == "B1"
    assert calls[0]["lang"] == "ru"

    async with session_factory() as session:
        sets = list(await session.scalars(select(VocabularySet)))
        assert len(sets) == 1
        assert sets[0].date == NOW.date()  # дата в часовом поясе пользователя
        assert len(sets[0].words) == 20

        assert list(await session.scalars(select(ActivityLog.kind))) == ["vocabulary"]
        streak = await StreakRepo(session).get(USER_ID)
        assert streak is not None
        assert streak.current_streak == 1


async def test_second_call_same_day_reuses_set_without_ai(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _create_user(session_factory)
    ai = FakeAIClient()

    first = await _get(session_factory, ai)
    second = await _get(session_factory, ai)

    assert second.reused is True
    assert second.words == first.words
    assert len(ai.calls_of("vocabulary")) == 1  # второго запроса к ИИ не было

    async with session_factory() as session:
        sets = list(await session.scalars(select(VocabularySet)))
        assert len(sets) == 1
        assert len(list(await session.scalars(select(ActivityLog)))) == 2
        streak = await StreakRepo(session).get(USER_ID)
        assert streak.current_streak == 1  # серия выросла только один раз


async def test_next_day_generates_new_set(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _create_user(session_factory)
    ai = _SequenceAIClient(
        [
            _words(*[f"day1_{index}" for index in range(20)]),
            _words(*[f"day2_{index}" for index in range(20)]),
        ]
    )

    await _get(session_factory, ai)
    tomorrow = await _get(session_factory, ai, now=NOW + timedelta(days=1))

    assert tomorrow.reused is False
    assert len(ai.calls_of("vocabulary")) == 2
    assert all(word.word.startswith("day2_") for word in tomorrow.words)

    async with session_factory() as session:
        sets = list(await session.scalars(select(VocabularySet)))
        assert [entry.date for entry in sets] == [NOW.date(), (NOW + timedelta(days=1)).date()]
        streak = await StreakRepo(session).get(USER_ID)
        assert streak.current_streak == 2


async def test_same_local_day_across_utc_midnight_reuses_set(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """00:30 и 23:30 по Самарканду — один местный день, набор тот же."""
    await _create_user(session_factory)
    ai = FakeAIClient()
    early = datetime(2026, 10, 18, 0, 30, tzinfo=SAMARKAND)
    late = datetime(2026, 10, 18, 23, 30, tzinfo=SAMARKAND)
    assert early.astimezone(timezone.utc).date() != late.astimezone(timezone.utc).date()

    await _get(session_factory, ai, now=early)
    daily = await _get(session_factory, ai, now=late)

    assert daily.reused is True
    assert len(ai.calls_of("vocabulary")) == 1


async def test_excludes_words_from_last_seven_days(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _create_user(session_factory)
    today = NOW.date()
    async with session_factory() as session:
        async with session.begin():
            repo = VocabularyRepo(session)
            await repo.save(
                USER_ID,
                today - timedelta(days=1),
                [{"word": "yesterdayword", "transcription": "/j/", "translation": "вчера"}],
            )
            await repo.save(
                USER_ID,
                today - timedelta(days=8),
                [{"word": "oldword", "transcription": "/o/", "translation": "старое"}],
            )

    ai = FakeAIClient()
    await _get(session_factory, ai)

    exclude_words = ai.calls_of("vocabulary")[0]["exclude_words"]
    assert "yesterdayword" in exclude_words
    assert "oldword" not in exclude_words  # выдан больше 7 дней назад


async def test_tops_up_when_ai_returns_fewer_words(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _create_user(session_factory)
    first = _words(*[f"w{index}" for index in range(12)])
    second = _words(*[f"w{index}" for index in range(8, 21)])
    ai = _SequenceAIClient([first, second])

    daily = await _get(session_factory, ai)

    assert len(daily.words) == 20
    assert len({word.word for word in daily.words}) == 20  # без дублей
    calls = ai.calls_of("vocabulary")
    assert [call["count"] for call in calls] == [20, 8]  # второй раз добрали 8


async def test_fails_when_ai_never_returns_enough_words(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _create_user(session_factory)
    ai = _SmallSetAIClient()

    with pytest.raises(AIResponseError) as error:
        await _get(session_factory, ai)

    assert error.value.user_message_key == "common.ai_bad_answer"
    assert len(ai.requested_counts) == 3  # не больше трёх попыток

    async with session_factory() as session:
        assert list(await session.scalars(select(VocabularySet))) == []
        assert list(await session.scalars(select(ActivityLog))) == []
        assert await StreakRepo(session).get(USER_ID) is None


async def test_ai_error_is_propagated_without_writes(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _create_user(session_factory)
    ai = FakeAIClient(error=AIRequestError("ИИ недоступен"))

    with pytest.raises(AIRequestError):
        await _get(session_factory, ai)

    async with session_factory() as session:
        assert list(await session.scalars(select(VocabularySet))) == []
        assert list(await session.scalars(select(ActivityLog))) == []


async def test_default_level_is_a2_when_unknown(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _create_user(session_factory, level=None)
    ai = FakeAIClient()

    daily = await _get(session_factory, ai)

    assert daily.level == "A2"
    assert daily.level_default is True
    assert ai.calls_of("vocabulary")[0]["level"] == "A2"


async def test_unknown_user_raises(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    with pytest.raises(ValueError):
        await _get(session_factory, FakeAIClient())
