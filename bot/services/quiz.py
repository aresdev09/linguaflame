"""Квиз: вопрос из банка или генерация через ИИ, счёт и тексты результата."""

import logging
from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from bot.locales import t
from bot.models import Question, User
from bot.repositories import QuestionRepo
from bot.services.ai_client import AIClient

logger = logging.getLogger(__name__)

DEFAULT_LEVEL = "A2"
# Вопросы ИИ сохраняем как грамматические: квиз спрашивает и грамматику, и лексику,
# а вид нужен банку вопросов для выборок (например, теста уровня).
GENERATED_QUESTION_KIND = "grammar"


async def next_quiz_question(
    session: AsyncSession,
    user: User,
    ai: AIClient,
    *,
    used_ids: Sequence[int] = (),
) -> Question:
    """Вопрос по уровню: сначала из банка, а если он исчерпан — новый от ИИ.

    Сгенерированный вопрос сразу сохраняется в `questions`, чтобы пополнить банк.
    """
    level = user.level or DEFAULT_LEVEL
    repo = QuestionRepo(session)

    bank = await repo.list_by_kind_level(level=level, limit=1, exclude_ids=used_ids)
    if bank:
        return bank[0]

    generated = await ai.generate_quiz(level, user.native_language)
    question = await repo.create(
        kind=GENERATED_QUESTION_KIND,
        level=level,
        text=generated.question,
        options=generated.options,
        correct_option=generated.correct,
        explanation=generated.explanation,
    )
    logger.info("Квиз: сгенерирован вопрос %s уровня %s", question.id, level)
    return question


@dataclass(frozen=True)
class QuizScore:
    """Итог одного ответа и накопленный счёт сессии."""

    is_correct: bool
    correct_count: int
    answered_count: int


def score_quiz_answer(
    question: Question,
    option: str,
    *,
    correct_count: int,
    answered_count: int,
) -> QuizScore:
    """Сверяет ответ с правильным вариантом и увеличивает счётчики."""
    is_correct = option == question.correct_option
    return QuizScore(
        is_correct=is_correct,
        correct_count=correct_count + int(is_correct),
        answered_count=answered_count + 1,
    )


def format_quiz_question(question: Question, number: int, lang: str) -> str:
    """Текст вопроса с номером в сессии."""
    return t("quiz.question", lang, number=number, text=question.text)


def format_quiz_feedback(
    question: Question,
    *,
    is_correct: bool,
    lang: str,
) -> str:
    """Верно/неверно, правильный вариант и пояснение."""
    lines = [
        t("quiz.correct" if is_correct else "quiz.wrong", lang),
        t(
            "quiz.correct_answer",
            lang,
            option=question.correct_option,
            answer=question.options.get(question.correct_option, ""),
        ),
    ]
    if question.explanation:
        lines.append(question.explanation)
    return "\n\n".join(lines)


def format_quiz_result(*, correct_count: int, answered_count: int, lang: str) -> str:
    """Итог сессии: сколько верных из отвеченных."""
    if answered_count == 0:
        return t("quiz.result_empty", lang)
    return t(
        "quiz.result",
        lang,
        correct=correct_count,
        total=answered_count,
    )
