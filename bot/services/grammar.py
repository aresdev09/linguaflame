"""Движок урока грамматики: темы, план, проверка упражнений и мини-теста.

Здесь нет aiogram: только правила движка урока.
Роутер /daily_grammar использует эти функции и хранит прогресс в БД.
"""

import re
from dataclasses import dataclass
from typing import Sequence

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from bot.locales import t
from bot.models import Lesson, User
from bot.repositories import LessonRepo
from bot.services.ai_client import AIClient
from bot.services.ai_errors import AIResponseError
from bot.services.ai_schemas import LessonPlan, LessonStep, LessonTestQuestion
from bot.services.grammar_topics import DEFAULT_LEVEL, GRAMMAR_TOPICS

# Размер одного сообщения шага и пауза между автоматическими сообщениями.
STEP_TEXT_LIMIT = 800
AUTO_MESSAGE_DELAY = 1.0

# Мини-тест ровно из 5 вопросов.
FINAL_TEST_SIZE = 5

# Вопросы, по которым отличаем вопрос пользователя от ответа на упражнение.
_QUESTION_WORDS = frozenset(
    {
        "why", "what", "how", "where", "when", "who", "which", "whose",
        "can", "could", "should", "would", "explain", "help", "please",
        "почему", "зачем", "как", "что", "где", "когда", "кто", "какой",
        "какая", "какие", "объясни", "помоги", "можно", "скажи",
    }
)

# Фразы «я не знаю» тоже считаются вопросом, а не ответом.
_HELP_PHRASES = frozenset(
    {
        "не знаю", "не понимаю", "не понял", "не поняла",
        "i dont know", "i don't know", "idk", "dont know", "don't know",
        "no idea",
    }
)

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?…])\s+")
_PUNCTUATION = re.compile(r"[.,!?;:\"'()\[\]{}«»]+")
_VARIANT_SPLIT = re.compile(r"\s*[/;|]\s*|\s+or\s+", re.IGNORECASE)


@dataclass(frozen=True)
class Mistake:
    """Ошибка в мини-тесте для итогового разбора."""

    number: int
    question: str
    option: str
    answer: str


def pick_topic(level: str | None, used_topics: Sequence[str]) -> str:
    """Выбирает тему уровня, не повторяя пройденные.

    Пока не пройден весь список, берётся первая непройденная тема.
    Когда список исчерпан, он начинается заново, но тема не повторяется
    подряд: первая тема не должна совпасть с последней пройденной.
    """
    topics = GRAMMAR_TOPICS.get(level or "", GRAMMAR_TOPICS[DEFAULT_LEVEL])
    used = set(used_topics)
    unused = [topic for topic in topics if topic not in used]
    if unused:
        return unused[0]
    last = used_topics[-1] if used_topics else None
    for topic in topics:
        if topic != last:
            return topic
    return topics[0]


def validate_lesson_plan(plan: LessonPlan) -> None:
    """Проверяет план урока после ответа ИИ."""
    if not plan.steps:
        raise AIResponseError("В плане урока нет шагов")
    if len(plan.final_test) != FINAL_TEST_SIZE:
        raise AIResponseError(
            f"В мини-тесте {len(plan.final_test)} вопросов вместо {FINAL_TEST_SIZE}"
        )


def load_plan(lesson: Lesson) -> LessonPlan:
    """Читает сохранённый план урока; битый JSON — ошибка ответа ИИ."""
    try:
        return LessonPlan.model_validate(lesson.plan)
    except ValidationError as exc:
        raise AIResponseError(f"Сохранённый план урока повреждён: {exc}") from exc


async def create_lesson(
    session: AsyncSession,
    user: User,
    ai: AIClient,
) -> tuple[Lesson, LessonPlan]:
    """Подбирает тему, заказывает план у ИИ и сохраняет урок в БД."""
    level = user.level or DEFAULT_LEVEL
    repo = LessonRepo(session)
    used_topics = await repo.list_topics(user.id, level)
    topic = pick_topic(level, used_topics)
    plan = await ai.generate_lesson_plan(level, user.native_language, topic=topic)
    validate_lesson_plan(plan)
    lesson = await repo.create(
        user_id=user.id,
        topic=topic,
        level=level,
        plan=plan.model_dump(),
    )
    return lesson, plan


def step_body(step: LessonStep) -> str:
    """Текст шага: у упражнения вопрос, у остальных — объяснение."""
    if step.type == "exercise":
        return step.question or ""
    return step.text or ""


def step_context(step: LessonStep) -> str:
    """Контекст текущего шага для вопроса пользователя."""
    body = step_body(step)
    if step.type == "exercise":
        return f"Exercise: {body}"
    return f"{step.type.capitalize()}: {body}"


def looks_like_question(text: str) -> bool:
    """Похоже ли сообщение на вопрос, а не на ответ упражнения."""
    cleaned = text.strip()
    if not cleaned:
        return False
    if cleaned.endswith("?"):
        return True
    if cleaned.casefold() in _HELP_PHRASES:
        return True
    first_word = cleaned.split()[0].casefold().strip("?!.,")
    return first_word in _QUESTION_WORDS


def is_exercise_answer(step: LessonStep, text: str) -> bool:
    """Ждём ли на этом шаге ответ на упражнение от пользователя."""
    return step.type == "exercise" and not looks_like_question(text)


def _normalize(text: str) -> str:
    text = text.replace("’", "'").casefold()
    text = _PUNCTUATION.sub(" ", text)
    return " ".join(text.split())


def check_exercise_answer(step: LessonStep, text: str) -> bool:
    """Сравнивает ответ пользователя с эталоном.

    Эталон может содержать варианты: «goes / go», «don't | do not».
    Сравнение нечувствительно к регистру, лишним пробелам и пунктуации.
    """
    if not step.answer:
        return False
    actual = _normalize(text)
    if not actual:
        return False
    for variant in _VARIANT_SPLIT.split(step.answer):
        normalized = _normalize(variant)
        if not normalized:
            continue
        if actual == normalized:
            return True
        if re.search(rf"(?<!\w){re.escape(normalized)}(?!\w)", actual):
            return True
    return False


def chunk_text(text: str, limit: int = STEP_TEXT_LIMIT) -> list[str]:
    """Делит текст шага на сообщения не длиннее limit символов."""
    text = text.strip()
    if not text:
        return [""]
    if len(text) <= limit:
        return [text]

    chunks: list[str] = []
    current = ""
    for paragraph in text.split("\n"):
        for unit in _SENTENCE_SPLIT.split(paragraph):
            for piece in _split_long_unit(unit, limit):
                if not piece:
                    continue
                candidate = f"{current}\n{piece}" if current else piece
                if len(candidate) > limit and current:
                    chunks.append(current)
                    current = piece
                else:
                    current = candidate
    if current:
        chunks.append(current)
    return chunks or [text[:limit]]


def _split_long_unit(unit: str, limit: int) -> list[str]:
    """Режет слишком длинное предложение по словам."""
    unit = unit.strip()
    if not unit:
        return [""]
    if len(unit) <= limit:
        return [unit]

    pieces: list[str] = []
    current = ""
    for word in unit.split():
        candidate = f"{current} {word}".strip()
        if len(candidate) > limit and current:
            pieces.append(current)
            current = word
        else:
            current = candidate
    if current:
        pieces.append(current)
    return pieces


def format_step(
    step: LessonStep,
    *,
    topic: str,
    number: int,
    total: int,
    lang: str,
) -> str:
    """Заголовок шага и его текст."""
    if step.type == "exercise":
        header = t("grammar.exercise_header", lang, topic=topic, number=number, total=total)
    else:
        header = t("grammar.step_header", lang, topic=topic, number=number, total=total)
    return f"{header}\n\n{step_body(step)}"


def format_final_question(
    question: LessonTestQuestion,
    *,
    number: int,
    total: int,
    lang: str,
) -> str:
    """Вопрос мини-теста; варианты показываются кнопками."""
    return (
        f"{t('grammar.test_header', lang, number=number, total=total)}"
        f"\n\n{question.question}"
    )


def format_test_feedback(question: LessonTestQuestion, option: str, *, lang: str) -> str:
    """Обратная связь на ответ в мини-тесте."""
    if option == question.correct:
        return t("grammar.test_correct", lang)
    return t(
        "grammar.test_wrong",
        lang,
        option=question.correct,
        answer=question.options[question.correct],
    )


def format_test_result(
    correct: int,
    total: int,
    mistakes: Sequence[Mistake],
    *,
    topic: str,
    lang: str,
) -> str:
    """Итог мини-теста: счёт и разбор ошибок."""
    lines = [t("grammar.test_result", lang, correct=correct, total=total)]
    if mistakes:
        lines.append(t("grammar.test_mistakes_title", lang))
        lines.extend(
            t(
                "grammar.test_mistake",
                lang,
                number=mistake.number,
                question=mistake.question,
                option=mistake.option,
                answer=mistake.answer,
            )
            for mistake in mistakes
        )
    else:
        lines.append(t("grammar.test_perfect", lang))
    lines.append(t("grammar.lesson_done", lang, topic=topic))
    return "\n\n".join(lines)
