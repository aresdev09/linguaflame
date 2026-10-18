"""Банк вопросов уровня: чтение JSON, проверка и загрузка в `questions`.

Формат файла `bot/data/level_questions.json`:
{
  "version": 1,
  "questions": [
    {"kind": "grammar", "level": "A1", "text": "...",
     "options": {"A": "...", "B": "...", "C": "..."},
     "correct_option": "B", "explanation": "..."}
  ]
}
"""

import json
import logging
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import LEVELS
from bot.repositories import QuestionRepo

logger = logging.getLogger(__name__)

BANK_PATH = Path(__file__).resolve().parents[1] / "data" / "level_questions.json"

QUESTION_KINDS = ("grammar", "vocabulary")
OPTION_LETTERS = ("A", "B", "C", "D")
MIN_OPTIONS = 3
MAX_OPTIONS = 4


class BankError(ValueError):
    """Банк вопросов отсутствует или заполнен неверно."""


@dataclass(frozen=True)
class BankQuestion:
    """Вопрос банка до записи в БД."""

    kind: str
    level: str
    text: str
    options: dict[str, str]
    correct_option: str
    explanation: str


@dataclass(frozen=True)
class InsertStats:
    """Результат загрузки банка в БД."""

    added: int
    skipped: int


@dataclass(frozen=True)
class BankCounts:
    """Количество вопросов банка по уровням и видам."""

    by_level_kind: dict[tuple[str, str], int]

    def for_level(self, level: str) -> int:
        return sum(
            count for (item_level, _), count in self.by_level_kind.items() if item_level == level
        )


def load_bank(path: Path = BANK_PATH) -> list[BankQuestion]:
    """Читает и разбирает JSON-файл банка, собирая понятные ошибки."""
    if not path.exists():
        raise BankError(f"Файл банка не найден: {path}")

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise BankError(f"Банк содержит некорректный JSON: {exc}") from exc

    if not isinstance(payload, dict) or not isinstance(payload.get("questions"), list):
        raise BankError("Банк должен быть объектом с полем questions-массивом")

    questions: list[BankQuestion] = []
    errors: list[str] = []
    for index, raw in enumerate(payload["questions"], start=1):
        item_errors: list[str] = []
        if not isinstance(raw, dict):
            errors.append(f"вопрос {index}: должен быть объектом")
            continue
        kind = raw.get("kind")
        level = raw.get("level")
        text = raw.get("text")
        options = raw.get("options")
        correct = raw.get("correct_option")
        explanation = raw.get("explanation")

        if kind not in QUESTION_KINDS:
            item_errors.append("kind должен быть grammar или vocabulary")
        if level not in LEVELS:
            item_errors.append(f"неизвестный level {level!r}")
        if not isinstance(text, str) or not text.strip():
            item_errors.append("text не заполнен")

        valid_options = False
        if not isinstance(options, dict) or not MIN_OPTIONS <= len(options) <= MAX_OPTIONS:
            item_errors.append("options должен содержать 3–4 варианта")
        elif set(options) - set(OPTION_LETTERS):
            item_errors.append("варианты должны называться A, B, C (D)")
        elif any(not isinstance(value, str) or not value.strip() for value in options.values()):
            item_errors.append("варианты должны быть непустыми строками")
        else:
            valid_options = True

        if valid_options and correct not in options:
            item_errors.append("correct_option отсутствует среди вариантов")
        if not isinstance(explanation, str) or not explanation.strip():
            item_errors.append("explanation не заполнен")

        if item_errors:
            errors.extend(f"вопрос {index}: {message}" for message in item_errors)
            continue
        questions.append(
            BankQuestion(
                kind=str(kind),
                level=str(level),
                text=text.strip(),
                options={letter: str(value).strip() for letter, value in options.items()},
                correct_option=str(correct),
                explanation=explanation.strip(),
            )
        )

    if errors:
        shown = "; ".join(errors[:10])
        more = "" if len(errors) <= 10 else f" (и ещё {len(errors) - 10})"
        raise BankError(f"Банк заполнен неверно: {shown}{more}")
    return questions


def validate_bank(
    questions: list[BankQuestion],
    *,
    min_per_level: int = 30,
) -> BankCounts:
    """Проверяет распределение и уникальность вопросов банка."""
    counts: dict[tuple[str, str], int] = {}
    seen: dict[str, int] = {}
    for index, question in enumerate(questions, start=1):
        key = (question.level, question.kind)
        counts[key] = counts.get(key, 0) + 1
        normalized = question.text.strip().casefold()
        if normalized in seen:
            raise BankError(
                f"Вопрос {index} повторяет вопрос {seen[normalized]}: {question.text!r}"
            )
        seen[normalized] = index

    for level in LEVELS:
        total = sum(count for (item_level, _), count in counts.items() if item_level == level)
        if total < min_per_level:
            raise BankError(f"Уровень {level}: {total} вопросов, нужно минимум {min_per_level}")
        for kind in QUESTION_KINDS:
            if counts.get((level, kind), 0) == 0:
                raise BankError(f"Уровень {level}: нет вопросов вида {kind}")
    return BankCounts(by_level_kind=counts)


async def insert_bank(
    session: AsyncSession,
    questions: list[BankQuestion],
) -> InsertStats:
    """Добавляет в `questions` только те вопросы, которых там ещё нет.

    Дубли определяются по паре (уровень, вид) и тексту без учёта регистра.
    Коммит делает вызывающий код (скрипт или тест).
    """
    repo = QuestionRepo(session)
    existing = await repo.list_by_kind_level()
    known = {(item.level, item.kind, item.text.strip().casefold()) for item in existing}

    added = 0
    skipped = 0
    for question in questions:
        key = (question.level, question.kind, question.text.strip().casefold())
        if key in known:
            skipped += 1
            continue
        await repo.create(
            kind=question.kind,
            level=question.level,
            text=question.text,
            options=question.options,
            correct_option=question.correct_option,
            explanation=question.explanation,
        )
        known.add(key)
        added += 1

    logger.info("Банк вопросов: добавлено %d, пропущено %d", added, skipped)
    return InsertStats(added=added, skipped=skipped)
