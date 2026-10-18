"""Тесты схем ответов ИИ и парсера JSON."""

import json

import pytest
from pydantic import ValidationError

from bot.services.ai_client import parse_json_payload, strip_markdown_fences
from bot.services.ai_schemas import (
    EssayCheck,
    LessonPlan,
    QuizQuestion,
    VocabularyResponse,
)


def test_quiz_question_requires_correct_option_to_exist() -> None:
    question = QuizQuestion(
        question="I ___ a student.",
        options={"A": "am", "B": "is", "C": "are"},
        correct="B",
        explanation="... ",
    )
    assert question.correct == "B"

    with pytest.raises(ValidationError):
        QuizQuestion(
            question="...",
            options={"A": "am"},
            correct="Z",
            explanation="...",
        )

    with pytest.raises(ValidationError):
        QuizQuestion(question="...", options={}, correct="A", explanation="...")


def test_vocabulary_word_requires_all_fields() -> None:
    response = VocabularyResponse(
        words=[{"word": "apple", "transcription": "/ˈæpl/", "translation": "яблоко"}]
    )
    assert response.words[0].translation == "яблоко"

    with pytest.raises(ValidationError):
        VocabularyResponse(words=[{"word": "apple"}])


def test_lesson_plan_step_rules() -> None:
    plan = LessonPlan(
        topic="Present Simple",
        steps=[{"type": "exercise", "question": "He ___ work.", "answer": "goes"}],
    )
    assert plan.final_test == []

    with pytest.raises(ValidationError):
        LessonPlan(topic="X", steps=[{"type": "exercise"}])

    with pytest.raises(ValidationError):
        LessonPlan(topic="X", steps=[{"type": "unknown-type", "text": "..."}])


def test_essay_criteria_must_be_between_zero_and_nine() -> None:
    payload = {
        "overall_band": 6.5,
        "criteria": {
            "task_response": 6.0,
            "coherence": 7.0,
            "lexical_resource": 6.5,
            "grammar": 6.5,
        },
        "weak_spots": [],
        "summary": "Неплохо.",
    }
    assert EssayCheck(**payload).criteria.coherence == 7.0

    payload["criteria"]["grammar"] = 12
    with pytest.raises(ValidationError):
        EssayCheck(**payload)


def test_strip_markdown_fences() -> None:
    assert strip_markdown_fences('```json\n{"a": 1}\n```') == '{"a": 1}'
    assert strip_markdown_fences('```\n{"a": 1}\n```') == '{"a": 1}'
    assert strip_markdown_fences('{"a": 1}') == '{"a": 1}'
    assert strip_markdown_fences('  {"a": 1}  ') == '{"a": 1}'


def test_parse_json_payload_handles_fences_and_extra_text() -> None:
    assert parse_json_payload('```\n{"a": 1}\n```') == {"a": 1}
    assert parse_json_payload('Вот ответ: {"a": 1} — готово') == {"a": 1}
    assert parse_json_payload(json.dumps({"a": 1})) == {"a": 1}

    with pytest.raises(json.JSONDecodeError):
        parse_json_payload("совсем не json")
