"""Тесты заглушки AI-клиента."""

import pytest

from bot.services.ai_client import AIClient
from bot.services.ai_errors import AIResponseError
from bot.services.fake_ai_client import FakeAIClient
from bot.services.ai_schemas import QuizQuestion

CLIENT_METHODS = (
    "generate_quiz",
    "generate_vocabulary",
    "generate_lesson_plan",
    "check_essay",
    "free_chat",
    "ask_in_lesson",
)


def test_fake_client_mirrors_real_client_methods() -> None:
    for name in CLIENT_METHODS:
        assert callable(getattr(FakeAIClient, name))
        assert callable(getattr(AIClient, name))


async def test_returns_prepared_answers_and_records_calls() -> None:
    client = FakeAIClient()

    quiz = await client.generate_quiz("B1", "ru")

    assert isinstance(quiz, QuizQuestion)
    assert quiz.correct == "A"
    assert client.calls == [{"task": "quiz", "level": "B1", "lang": "ru"}]


async def test_vocabulary_contains_twenty_words() -> None:
    client = FakeAIClient()

    vocabulary = await client.generate_vocabulary("A2", "ru", count=20)

    assert len(vocabulary.words) == 20
    assert client.calls_of("vocabulary")[0]["count"] == 20


async def test_lesson_plan_and_essay_defaults() -> None:
    client = FakeAIClient()

    plan = await client.generate_lesson_plan("B1", "en")
    essay = await client.check_essay("B2", "en", "My essay text")

    assert plan.topic
    assert plan.steps
    assert 0 <= essay.overall_band <= 9
    assert client.calls_of("essay_check")[0]["text"] == "My essay text"


async def test_chat_answers_are_text() -> None:
    client = FakeAIClient(chat="Привет!")

    answer = await client.free_chat("A2", "ru", text="привет")

    assert answer == "Привет!"
    lesson_answer = await client.ask_in_lesson(
        "A2", "ru", step_text="Present Simple", question="а как?"
    )
    assert isinstance(lesson_answer, str)


async def test_error_injection_breaks_calls() -> None:
    client = FakeAIClient(error=AIResponseError("ИИ ответил не так, как ожидалось"))

    with pytest.raises(AIResponseError):
        await client.generate_quiz("B1", "ru")

    assert client.calls_of("quiz")


async def test_close_is_noop() -> None:
    await FakeAIClient().close()