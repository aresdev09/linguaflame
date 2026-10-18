"""Тесты банка вопросов уровня (задачи 8.1 и 8.2)."""

import json
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import LEVELS
from bot.repositories import QuestionRepo
from bot.services.question_bank import (
    BANK_PATH,
    BankError,
    insert_bank,
    load_bank,
    validate_bank,
)


def test_real_bank_has_minimum_30_questions_per_level() -> None:
    questions = load_bank(BANK_PATH)
    counts = validate_bank(questions)

    assert len(questions) == 180
    for level in LEVELS:
        assert counts.by_level_kind[(level, "grammar")] == 15
        assert counts.by_level_kind[(level, "vocabulary")] == 15
        assert counts.for_level(level) == 30


def test_bank_rejects_unknown_correct_option(tmp_path: Path) -> None:
    payload = {
        "version": 1,
        "questions": [
            {
                "kind": "grammar",
                "level": "A1",
                "text": "I ___ a student.",
                "options": {"A": "am", "B": "is", "C": "are"},
                "correct_option": "D",
                "explanation": "С I — am.",
            }
        ],
    }
    path = tmp_path / "bad_bank.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(BankError, match="correct_option"):
        load_bank(path)


def test_validate_bank_rejects_duplicates() -> None:
    questions = load_bank(BANK_PATH)
    with pytest.raises(BankError, match="повторяет"):
        validate_bank([questions[0], questions[0], *questions[1:]], min_per_level=0)


async def test_insert_bank_is_idempotent(session: AsyncSession) -> None:
    questions = load_bank(BANK_PATH)

    first = await insert_bank(session, questions)
    second = await insert_bank(session, questions)
    await session.commit()

    assert first.added == 180
    assert second.added == 0
    assert second.skipped == 180
    assert len(await QuestionRepo(session).list_by_kind_level()) == 180
