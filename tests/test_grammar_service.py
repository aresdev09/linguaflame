"""Тесты движка урока грамматики."""

import pytest

from bot.config import LEVELS
from bot.services.ai_errors import AIResponseError
from bot.services.ai_schemas import LessonPlan, LessonStep
from bot.services.grammar import (
    Mistake,
    check_exercise_answer,
    chunk_text,
    format_test_result,
    looks_like_question,
    pick_topic,
    step_context,
    validate_lesson_plan,
)
from bot.services.grammar_topics import GRAMMAR_TOPICS


def test_topics_cover_all_levels() -> None:
    assert set(GRAMMAR_TOPICS) == set(LEVELS)
    for topics in GRAMMAR_TOPICS.values():
        assert len(topics) == len(set(topics)) == 15


def test_pick_topic_skips_used_and_avoids_repeats() -> None:
    topics = GRAMMAR_TOPICS["A1"]

    assert pick_topic("A1", []) == topics[0]
    assert pick_topic("A1", [topics[0]]) == topics[1]
    assert pick_topic("A1", list(topics[:5])) == topics[5]
    # Все темы пройдены: список начинается заново, но не с последней темы.
    assert pick_topic("A1", list(topics)) != topics[-1]
    assert pick_topic("A1", [topics[-1]]) == topics[0]
    # Неизвестный уровень — список уровня по умолчанию.
    assert pick_topic("Z9", []) == GRAMMAR_TOPICS["A2"][0]


def test_validate_lesson_plan_requires_steps_and_five_questions() -> None:
    with pytest.raises(AIResponseError):
        validate_lesson_plan(
            LessonPlan(
                topic="X",
                steps=[{"type": "explanation", "text": "..."}],
                final_test=[],
            )
        )

    with pytest.raises(AIResponseError):
        validate_lesson_plan(
            LessonPlan(
                topic="X",
                steps=[],
                final_test=[{"question": "?", "options": {"A": "a", "B": "b"}, "correct": "A"}],
            )
        )

    valid = LessonPlan(
        topic="X",
        steps=[{"type": "explanation", "text": "..."}],
        final_test=[
            {
                "question": f"Question {index}",
                "options": {"A": "a", "B": "b", "C": "c"},
                "correct": "B",
            }
            for index in range(5)
        ],
    )
    validate_lesson_plan(valid)


def test_check_exercise_answer_ignores_case_and_punctuation() -> None:
    step = LessonStep(type="exercise", question="He ___ to work.", answer="goes")

    assert check_exercise_answer(step, "Goes.")
    assert check_exercise_answer(step, "  GOES ")
    assert not check_exercise_answer(step, "go")
    assert not check_exercise_answer(step, "")


def test_check_exercise_answer_supports_variants() -> None:
    step = LessonStep(type="exercise", question="___ you like tea?", answer="don't / do not")

    assert check_exercise_answer(step, "do not")
    assert check_exercise_answer(step, "Don't")
    assert not check_exercise_answer(step, "does not")


def test_looks_like_question() -> None:
    assert looks_like_question("Почему здесь goes?")
    assert looks_like_question("Why does he go?")
    assert looks_like_question("What is Present Simple")
    assert looks_like_question("Не знаю")
    assert not looks_like_question("goes")
    assert not looks_like_question("do not")


def test_chunk_text_respects_limit_and_keeps_words() -> None:
    text = (
        "Present Simple описывает регулярные действия, которые происходят "
        "каждый день или по расписанию. Мы используем его с наречиями "
        "частоты, например always, often, sometimes и never."
    )
    chunks = chunk_text(text * 5, limit=80)

    assert len(chunks) > 1
    assert all(len(chunk) <= 80 for chunk in chunks)
    words = set(chunk_text(text, limit=80)[0].casefold().split())
    rebuilt = " ".join(chunks).casefold().split()
    assert words <= set(rebuilt)


def test_short_text_is_one_chunk() -> None:
    assert chunk_text("Короткий шаг", limit=800) == ["Короткий шаг"]


def test_step_context_marks_exercise() -> None:
    explanation = LessonStep(type="explanation", text="Теория")
    exercise = LessonStep(type="exercise", question="He ___ work.", answer="goes")

    assert step_context(explanation) == "Explanation: Теория"
    assert step_context(exercise) == "Exercise: He ___ work."


def test_format_test_result_lists_mistakes() -> None:
    mistakes = [
        Mistake(
            number=2,
            question="They ___ football.",
            option="A",
            answer="play",
        )
    ]
    text = format_test_result(4, 5, mistakes, topic="Present Simple", lang="ru")

    assert "4 из 5" in text
    assert "Разбор ошибок" in text
    assert "2. They ___ football." in text
    assert "A) play" in text
    assert "Present Simple" in text
