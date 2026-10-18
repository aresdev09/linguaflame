"""Тест уровня: выбор 50 вопросов, подсчёт баллов и тексты.

Правила:
- 50 вопросов по распределению из конфига, грамматика и словарь вперемешку;
- вес правильного ответа зависит от уровня вопроса;
- быстрый ответ даёт бонус до +10%, ответ быстрее 2 секунд на B1+
  считается угадыванием, ответ дольше 60 секунд бонуса не получает;
- итоговый процент переводится в уровень по порогам из конфига;
- дополнительная проверка согласованности может поднять уровень.
"""

import logging
import random
from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import (
    CONSISTENCY_MIN_ACCURACY,
    LEVEL_SPEED_NORMS_SEC,
    LEVEL_TEST_DISTRIBUTION,
    LEVEL_THRESHOLDS,
    LEVEL_WEIGHTS,
    LEVELS,
    SPEED_BONUS,
    SPEED_GUESSING_SEC,
    SPEED_SLOW_SEC,
)
from bot.locales import t
from bot.models import Question, User
from bot.repositories import QuestionRepo
from bot.services.timezones import as_utc, resolve_timezone

logger = logging.getLogger(__name__)

# Уровни, где ответ быстрее SPEED_GUESSING_SEC считается угадыванием.
GUESSING_LEVELS = frozenset(("B1", "B2", "C1", "C2"))


class InsufficientQuestionsError(RuntimeError):
    """В банке не хватает вопросов для теста."""

    def __init__(self, level: str, kind: str, needed: int, available: int) -> None:
        self.level = level
        self.kind = kind
        self.needed = needed
        self.available = available
        super().__init__(
            f"Уровень {level}, вид {kind}: нужно {needed}, в банке {available}"
        )


class MissingQuestionsError(RuntimeError):
    """Вопрос из сохранённого теста не найден в банке."""

    def __init__(self, question_ids: Sequence[int]) -> None:
        self.question_ids = list(question_ids)
        super().__init__(f"В банке нет вопросов: {self.question_ids}")


async def select_test_questions(
    session: AsyncSession,
    *,
    rng: random.Random | None = None,
    distribution: dict[str, int] | None = None,
) -> list[Question]:
    """Набирает вопросы по распределению уровней, без повторов."""
    chooser = rng or random.Random()
    plan = distribution or LEVEL_TEST_DISTRIBUTION
    repo = QuestionRepo(session)
    selected: list[Question] = []

    for level, total in plan.items():
        grammar_count = total // 2
        vocabulary_count = total - grammar_count
        for kind, needed in (
            ("grammar", grammar_count),
            ("vocabulary", vocabulary_count),
        ):
            pool = await repo.list_by_kind_level(kind=kind, level=level)
            if len(pool) < needed:
                raise InsufficientQuestionsError(level, kind, needed, len(pool))
            selected.extend(chooser.sample(pool, needed))

    chooser.shuffle(selected)
    return selected


async def get_questions_by_ids(
    session: AsyncSession,
    question_ids: Sequence[int],
) -> list[Question]:
    """Возвращает вопросы в сохранённом порядке теста."""
    if not question_ids:
        return []
    result = await session.execute(
        select(Question).where(Question.id.in_(list(question_ids)))
    )
    by_id = {question.id: question for question in result.scalars().all()}
    missing = [question_id for question_id in question_ids if question_id not in by_id]
    if missing:
        raise MissingQuestionsError(missing)
    return [by_id[question_id] for question_id in question_ids]


@dataclass(frozen=True)
class LevelAnswer:
    """Ответ теста в виде, нужном для подсчёта."""

    level: str
    kind: str
    is_correct: bool
    answer_time_sec: int


@dataclass(frozen=True)
class LevelTestResult:
    """Итог теста уровня."""

    level: str
    percent: float
    correct_count: int
    total_count: int
    average_time_sec: float
    total_time_sec: int
    grammar_correct: int
    grammar_total: int
    vocabulary_correct: int
    vocabulary_total: int

    @property
    def accuracy_percent(self) -> float:
        if self.total_count == 0:
            return 0.0
        return self.correct_count / self.total_count * 100


def score_answer(
    level: str,
    *,
    is_correct: bool,
    answer_time_sec: int,
    weights: dict[str, float] | None = None,
    norms: dict[str, int] | None = None,
) -> float:
    """Балл за один ответ с поправкой на скорость."""
    if not is_correct:
        return 0.0

    level_weights = weights or LEVEL_WEIGHTS
    level_norms = norms or LEVEL_SPEED_NORMS_SEC
    base = level_weights[level]

    if answer_time_sec > SPEED_SLOW_SEC:
        return base
    if level in GUESSING_LEVELS and answer_time_sec < SPEED_GUESSING_SEC:
        return base
    if answer_time_sec <= level_norms[level]:
        return base * (1 + SPEED_BONUS)
    return base


def max_test_score(levels: Sequence[str]) -> float:
    """Максимум баллов: все ответы верные и быстрые."""
    return sum(LEVEL_WEIGHTS[level] * (1 + SPEED_BONUS) for level in levels)


def level_from_percent(percent: float) -> str:
    """Переводит итоговый процент в уровень по порогам из конфига."""
    for minimum, level in reversed(LEVEL_THRESHOLDS):
        if percent >= minimum:
            return level
    return LEVELS[0]


def _consistency_level(answers: Sequence[LevelAnswer]) -> str | None:
    """Самый высокий уровень, где точность не ниже порога согласованности."""
    by_level: dict[str, list[bool]] = {level: [] for level in LEVELS}
    for answer in answers:
        if answer.level in by_level:
            by_level[answer.level].append(answer.is_correct)

    best: str | None = None
    for level in LEVELS:
        results = by_level[level]
        if not results:
            continue
        accuracy = sum(results) / len(results)
        if accuracy >= CONSISTENCY_MIN_ACCURACY:
            best = level
    return best


def compute_level_test_result(answers: Sequence[LevelAnswer]) -> LevelTestResult:
    """Считает взвешенный процент, уровень и статистику по разделам."""
    if not answers:
        raise ValueError("Нельзя посчитать результат без ответов")

    total_time = sum(answer.answer_time_sec for answer in answers)
    weighted = sum(
        score_answer(
            answer.level,
            is_correct=answer.is_correct,
            answer_time_sec=answer.answer_time_sec,
        )
        for answer in answers
    )
    maximum = max_test_score([answer.level for answer in answers])
    percent = weighted / maximum * 100

    threshold_level = level_from_percent(percent)
    consistent_level = _consistency_level(answers)
    final_level = threshold_level
    if consistent_level is not None:
        if LEVELS.index(consistent_level) > LEVELS.index(final_level):
            final_level = consistent_level

    grammar = [answer for answer in answers if answer.kind == "grammar"]
    vocabulary = [answer for answer in answers if answer.kind == "vocabulary"]

    result = LevelTestResult(
        level=final_level,
        percent=round(percent, 1),
        correct_count=sum(answer.is_correct for answer in answers),
        total_count=len(answers),
        average_time_sec=round(total_time / len(answers), 1),
        total_time_sec=total_time,
        grammar_correct=sum(answer.is_correct for answer in grammar),
        grammar_total=len(grammar),
        vocabulary_correct=sum(answer.is_correct for answer in vocabulary),
        vocabulary_total=len(vocabulary),
    )
    logger.info(
        "Тест уровня: %s, %.1f%%, верных %d из %d",
        result.level,
        result.percent,
        result.correct_count,
        result.total_count,
    )
    return result


def _section_percent(correct: int, total: int) -> float:
    return correct / total * 100 if total else 0.0


def format_level_question(
    question: Question,
    number: int,
    total: int,
    lang: str,
) -> str:
    """Текст вопроса теста с прогрессом."""
    return t(
        "level.question",
        lang,
        number=number,
        total=total,
        text=question.text,
    )


def format_retake_prompt(user: User, lang: str) -> str:
    """Подтверждение повторной сдачи с текущим уровнем и датой."""
    date_text = "—"
    if user.level_tested_at is not None:
        tested_at = as_utc(user.level_tested_at)
        timezone_info = resolve_timezone(user.timezone, user_id=user.id)
        date_text = tested_at.astimezone(timezone_info).strftime("%d.%m.%Y")
    return t(
        "level.retake",
        lang,
        level=user.level or "—",
        date=date_text,
    )


def format_level_result(result: LevelTestResult, lang: str) -> str:
    """Сообщение с уровнем, точностью, временем и сильными/слабыми сторонами."""
    grammar_percent = _section_percent(result.grammar_correct, result.grammar_total)
    vocabulary_percent = _section_percent(
        result.vocabulary_correct, result.vocabulary_total
    )
    lines = [
        t(
            "level.result",
            lang,
            level=result.level,
            correct=result.correct_count,
            total=result.total_count,
            accuracy=result.accuracy_percent,
            average=result.average_time_sec,
            grammar=grammar_percent,
            vocabulary=vocabulary_percent,
        )
    ]

    if abs(grammar_percent - vocabulary_percent) < 0.5:
        lines.append(t("level.result_balanced", lang))
    else:
        weak_key = "level.topic.vocabulary"
        strong_key = "level.topic.grammar"
        if vocabulary_percent > grammar_percent:
            weak_key = "level.topic.grammar"
            strong_key = "level.topic.vocabulary"
        lines.append(
            t("level.result_strength", lang, topic=t(strong_key, lang))
        )
        lines.append(t("level.result_weakness", lang, topic=t(weak_key, lang)))

    return "\n".join(lines)
