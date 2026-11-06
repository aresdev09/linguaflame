"""Тесты сервиса квиза."""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.locales import t
from bot.models import Question
from bot.repositories import QuestionRepo, UserRepo
from bot.services.fake_ai_client import FakeAIClient
from bot.services.quiz import (
    format_quiz_feedback,
    format_quiz_result,
    next_quiz_question,
    score_quiz_answer,
)

USER_ID = 701


async def _create_user(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    level: str | None = "B1",
    native_language: str = "ru",
    user_id: int = USER_ID,
) -> None:
    async with session_factory() as session:
        async with session.begin():
            repo = UserRepo(session)
            await repo.create(user_id, native_language=native_language)
            if level is not None:
                await repo.set_level(user_id, level, datetime.now(UTC))


async def _seed_question(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    text: str,
    level: str = "B1",
    correct: str = "A",
    explanation: str = "Пояснение",
    language: str = "ru",
) -> int:
    async with session_factory() as session:
        async with session.begin():
            question = await QuestionRepo(session).create(
                kind="grammar",
                level=level,
                text=text,
                options={"A": "am", "B": "is", "C": "are"},
                correct_option=correct,
                explanation=explanation,
                language=language,
            )
            return question.id


async def test_next_question_prefers_bank_and_skips_used(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _create_user(session_factory)
    first_id = await _seed_question(session_factory, text="Первый вопрос")
    second_id = await _seed_question(session_factory, text="Второй вопрос")
    ai = FakeAIClient()

    async with session_factory() as session:
        async with session.begin():
            user = await UserRepo(session).get(USER_ID)
            assert user is not None
            first = await next_quiz_question(session, user, ai)
            second = await next_quiz_question(session, user, ai, used_ids=[first.id])

    assert first.id == first_id
    assert second.id == second_id
    assert ai.calls == []  # банк пополнился, ИИ не понадобился


async def test_next_question_generates_and_saves_when_bank_is_empty(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _create_user(session_factory)
    ai = FakeAIClient()

    async with session_factory() as session:
        async with session.begin():
            user = await UserRepo(session).get(USER_ID)
            assert user is not None
            question = await next_quiz_question(session, user, ai)

            saved = list(await session.scalars(select(Question)))
            assert len(saved) == 1
            assert saved[0].id == question.id
            assert saved[0].level == "B1"
            assert saved[0].text == ai.quiz.question
            assert saved[0].correct_option == ai.quiz.correct

    assert ai.calls_of("quiz") == [{"task": "quiz", "level": "B1", "lang": "ru"}]


async def test_next_question_uses_uz_bank_for_uz_user(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _create_user(session_factory, native_language="uz")
    await _seed_question(session_factory, text="Русский вопрос", language="ru")
    uz_id = await _seed_question(session_factory, text="Uzbek savol", language="uz")
    ai = FakeAIClient()

    async with session_factory() as session:
        async with session.begin():
            user = await UserRepo(session).get(USER_ID)
            assert user is not None
            question = await next_quiz_question(session, user, ai)

    assert question.id == uz_id
    assert ai.calls == []


async def test_next_question_falls_back_to_russian_bank(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _create_user(session_factory, native_language="uz")
    ru_id = await _seed_question(session_factory, text="Русский вопрос", language="ru")
    ai = FakeAIClient()

    async with session_factory() as session:
        async with session.begin():
            user = await UserRepo(session).get(USER_ID)
            assert user is not None
            question = await next_quiz_question(session, user, ai)

    assert question.id == ru_id
    assert ai.calls == []


async def test_generated_question_is_saved_in_user_language(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _create_user(session_factory, native_language="uz")
    ai = FakeAIClient()

    async with session_factory() as session:
        async with session.begin():
            user = await UserRepo(session).get(USER_ID)
            assert user is not None
            question = await next_quiz_question(session, user, ai)
            saved = await session.get(Question, question.id)

    assert saved is not None
    assert saved.language == "uz"


async def test_next_question_uses_a2_without_level(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _create_user(session_factory, level=None)
    ai = FakeAIClient()

    async with session_factory() as session:
        async with session.begin():
            user = await UserRepo(session).get(USER_ID)
            assert user is not None
            question = await next_quiz_question(session, user, ai)

    assert question.level == "A2"
    assert ai.calls_of("quiz")[0]["level"] == "A2"


def _question() -> Question:
    return Question(
        id=1,
        kind="grammar",
        level="B1",
        text="I ___ a student.",
        options={"A": "am", "B": "is", "C": "are"},
        correct_option="A",
        explanation="С I используется am.",
    )


def test_score_counts_correct_and_wrong_answers() -> None:
    question = _question()

    correct = score_quiz_answer(question, "A", correct_count=2, answered_count=5)
    assert correct.is_correct is True
    assert correct.correct_count == 3
    assert correct.answered_count == 6

    wrong = score_quiz_answer(question, "B", correct_count=2, answered_count=5)
    assert wrong.is_correct is False
    assert wrong.correct_count == 2
    assert wrong.answered_count == 6


def test_feedback_contains_correct_option_and_explanation() -> None:
    question = _question()

    right = format_quiz_feedback(question, is_correct=True, lang="ru")
    wrong = format_quiz_feedback(question, is_correct=False, lang="ru")

    assert right.startswith(t("quiz.correct", "ru"))
    assert wrong.startswith(t("quiz.wrong", "ru"))
    assert t("quiz.correct_answer", "ru", option="A", answer="am") in right
    assert "С I используется am." in wrong


def test_result_text() -> None:
    assert format_quiz_result(correct_count=1, answered_count=2, lang="ru") == t(
        "quiz.result", "ru", correct=1, total=2
    )
    assert format_quiz_result(correct_count=0, answered_count=0, lang="en") == t(
        "quiz.result_empty", "en"
    )
