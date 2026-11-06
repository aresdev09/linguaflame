"""Тесты банка вопросов уровня (задачи 8.1 и 8.2)."""

import json
import re
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import LEVELS
from bot.repositories import QuestionRepo
from bot.services.level_test import select_test_questions
from bot.services.question_bank import (
    BANK_FILES,
    BANK_PATH,
    UZ_BANK_PATH,
    BankError,
    insert_bank,
    load_bank,
    validate_bank,
)


def test_all_bank_files_exist_and_are_valid() -> None:
    assert set(BANK_FILES) == {"ru", "uz"}
    for path in BANK_FILES.values():
        assert path.exists()


@pytest.mark.parametrize("bank_path", [BANK_PATH, UZ_BANK_PATH], ids=["ru", "uz"])
def test_real_bank_has_minimum_30_questions_per_level(bank_path) -> None:
    questions = load_bank(bank_path)
    counts = validate_bank(questions)

    assert len(questions) == 180
    for level in LEVELS:
        assert counts.by_level_kind[(level, "grammar")] == 15
        assert counts.by_level_kind[(level, "vocabulary")] == 15
        assert counts.for_level(level) == 30


def test_uz_bank_has_no_cyrillic() -> None:
    cyrillic = re.compile(r"[А-Яа-яЁё]")
    for question in load_bank(UZ_BANK_PATH):
        assert not cyrillic.search(question.text)
        assert not cyrillic.search(question.explanation)
        for value in question.options.values():
            assert not cyrillic.search(value)


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


async def test_insert_bank_stores_language_and_keeps_banks_separate(
    session: AsyncSession,
) -> None:
    ru_questions = load_bank(BANK_PATH)
    uz_questions = load_bank(UZ_BANK_PATH)

    ru_first = await insert_bank(session, ru_questions, language="ru")
    uz_first = await insert_bank(session, uz_questions, language="uz")
    uz_again = await insert_bank(session, uz_questions, language="uz")
    await session.commit()

    assert (ru_first.added, ru_first.skipped) == (180, 0)
    assert (uz_first.added, uz_first.skipped) == (180, 0)
    assert (uz_again.added, uz_again.skipped) == (0, 180)
    assert len(await QuestionRepo(session).list_by_kind_level(language="ru")) == 180
    assert len(await QuestionRepo(session).list_by_kind_level(language="uz")) == 180


async def test_select_test_questions_prefers_user_language(
    session: AsyncSession,
) -> None:
    await insert_bank(session, load_bank(BANK_PATH), language="ru")
    await insert_bank(session, load_bank(UZ_BANK_PATH), language="uz")
    await session.commit()

    selected = await select_test_questions(session, language="uz")

    assert len(selected) == 50
    assert {question.language for question in selected} == {"uz"}


async def test_select_test_questions_falls_back_to_russian_bank(
    session: AsyncSession,
) -> None:
    await insert_bank(session, load_bank(BANK_PATH), language="ru")
    await session.commit()

    selected = await select_test_questions(session, language="uz")

    assert len(selected) == 50
    assert {question.language for question in selected} == {"ru"}
