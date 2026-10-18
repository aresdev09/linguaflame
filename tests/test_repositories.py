"""Тесты репозиториев на SQLite в памяти."""

from datetime import timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models import User, utcnow
from bot.repositories import (
    ActivityRepo,
    EssayRepo,
    LessonRepo,
    QuestionRepo,
    StreakRepo,
    UserRepo,
)


async def test_user_get_or_create_does_not_duplicate(session: AsyncSession) -> None:
    repo = UserRepo(session)
    telegram_id = 5_123_456_789

    user = await repo.get_or_create(telegram_id, username="nick")
    again = await repo.get_or_create(telegram_id)

    assert user.id == telegram_id
    assert again.id == telegram_id
    assert (await repo.get(telegram_id)).username == "nick"
    count = await session.scalar(select(func.count()).select_from(User))
    assert count == 1


async def test_user_get_returns_none_for_unknown_user(session: AsyncSession) -> None:
    assert await UserRepo(session).get(42) is None


async def test_user_defaults_are_utc_and_english(session: AsyncSession) -> None:
    user = await UserRepo(session).get_or_create(1)

    assert user.timezone == "UTC"
    assert user.native_language == "en"
    assert user.level is None
    assert user.level_tested_at is None
    assert user.created_at is not None


async def test_user_update_profile_and_set_level(session: AsyncSession) -> None:
    repo = UserRepo(session)
    user = await repo.get_or_create(1)

    await repo.update_profile(1, native_language="ru", timezone="Asia/Samarkand")
    await session.refresh(user)
    assert user.native_language == "ru"
    assert user.timezone == "Asia/Samarkand"
    assert user.username is None

    await repo.set_level(1, "B1", utcnow())
    await session.refresh(user)
    assert user.level == "B1"
    assert user.level_tested_at is not None


async def test_streak_get_or_create_and_update(session: AsyncSession) -> None:
    await UserRepo(session).get_or_create(1)
    repo = StreakRepo(session)

    streak = await repo.get_or_create(1)
    assert streak.current_streak == 0
    assert streak.best_streak == 0

    today = utcnow().date()
    await repo.update(1, current_streak=3, best_streak=5, last_activity_date=today)
    await session.refresh(streak)
    assert streak.current_streak == 3
    assert streak.best_streak == 5
    assert streak.last_activity_date == today


async def test_question_create_and_filter(session: AsyncSession) -> None:
    repo = QuestionRepo(session)
    first = await repo.create(
        kind="grammar",
        level="A1",
        text="I ___ a student.",
        options={"A": "am", "B": "is", "C": "are"},
        correct_option="A",
        explanation="С I глагол am",
    )
    second = await repo.create(
        kind="vocabulary",
        level="A2",
        text="Choose the synonym of 'big'.",
        options={"A": "small", "B": "large", "C": "old"},
        correct_option="B",
    )
    third = await repo.create(
        kind="grammar",
        level="A1",
        text="She ___ to school.",
        options={"A": "go", "B": "goes", "C": "going"},
        correct_option="B",
    )

    grammar_a1 = await repo.list_by_kind_level(kind="grammar", level="A1")
    assert [question.id for question in grammar_a1] == [first.id, third.id]

    without_first = await repo.list_by_kind_level(
        kind="grammar", level="A1", exclude_ids=[first.id]
    )
    assert [question.id for question in without_first] == [third.id]

    vocabulary = await repo.list_by_kind_level(kind="vocabulary")
    assert [question.id for question in vocabulary] == [second.id]

    assert len(await repo.list_by_kind_level(limit=2)) == 2

    saved = await repo.get(first.id)
    assert saved.options["A"] == "am"
    assert saved.correct_option == "A"


async def test_lesson_create_and_progress(session: AsyncSession) -> None:
    await UserRepo(session).get_or_create(1)
    repo = LessonRepo(session)

    lesson = await repo.create(
        user_id=1,
        topic="Present Perfect",
        level="B1",
        plan={"steps": [{"type": "explanation", "text": "..."}]},
    )
    assert lesson.status == "active"
    assert lesson.current_step == 0

    active = await repo.get_active(1)
    assert active is not None
    assert active.id == lesson.id

    await repo.update(lesson.id, current_step=2)
    await session.refresh(lesson)
    assert lesson.current_step == 2

    await repo.update(lesson.id, status="done")
    await session.refresh(lesson)
    assert lesson.status == "done"
    assert await repo.get_active(1) is None


async def test_essay_create_and_history(session: AsyncSession) -> None:
    await UserRepo(session).get_or_create(1)
    repo = EssayRepo(session)

    first = await repo.create(
        user_id=1,
        text="First essay",
        score_overall=5.5,
        score_json={"task_response": 5.0},
        feedback="Расширьте аргументацию",
    )
    second = await repo.create(
        user_id=1,
        text="Second essay",
        score_overall=6.5,
        score_json={"task_response": 6.5},
        feedback="Хорошая структура",
    )

    history = await repo.list_by_user(1)
    assert [essay.id for essay in history] == [second.id, first.id]

    saved = await repo.get(first.id)
    assert saved.score_overall == 5.5
    assert saved.score_json == {"task_response": 5.0}


async def test_activity_add_and_count_since(session: AsyncSession) -> None:
    await UserRepo(session).get_or_create(1)
    await UserRepo(session).get_or_create(2)
    repo = ActivityRepo(session)

    await repo.add(1, "quiz")
    await repo.add(1, "vocabulary")
    await repo.add(2, "chat")

    week_ago = utcnow() - timedelta(days=7)
    assert await repo.count_since(1, week_ago) == 2
    assert await repo.count_since(2, week_ago) == 1

    tomorrow = utcnow() + timedelta(days=1)
    assert await repo.count_since(1, tomorrow) == 0


async def test_activity_created_at_is_set(session: AsyncSession) -> None:
    await UserRepo(session).get_or_create(1)

    entry = await ActivityRepo(session).add(1, "quiz")

    assert entry.created_at is not None


async def test_foreign_keys_are_enforced(session: AsyncSession) -> None:
    """Тесты проверяют ссылки так же, как это делает PostgreSQL в проде."""
    with pytest.raises(IntegrityError):
        await StreakRepo(session).get_or_create(999)
