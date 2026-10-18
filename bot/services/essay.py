"""Проверка эссе по критериям IELTS Writing Task 2.

Правила:
- текст от 80 до 500 слов, иначе отказ с объяснением;
- текст уходит в ИИ в тегах `<user_text>` как данные, а не как инструкции;
- общий балл считается кодом (среднее четырёх критериев, округление до 0.5),
  а не берётся из ответа модели;
- разбор: до 7 слабых мест с цитатой и исправлением, сильные стороны,
  главный совет и оговорка про ориентировочную оценку;
- результат сохраняется в `essays`, учебное действие растёт в серии дней;
- `users.level` этот сценарий не меняет.
"""

import html
import logging
import math
import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from bot.locales import t
from bot.models import Essay, User
from bot.repositories import EssayRepo
from bot.services.ai_client import AIClient
from bot.services.ai_schemas import EssayCheck
from bot.services.streak import register_activity
from bot.services.timezones import as_utc

logger = logging.getLogger(__name__)

# Ограничения длины эссе в словах.
MIN_WORDS = 80
MAX_WORDS = 500

# Не больше 7 слабых мест, самые важные первыми.
MAX_WEAK_SPOTS = 7

# Шаг баллов IELTS: общий балл округляется до ближайших 0.5.
BAND_STEP = 0.5

# Уровень по умолчанию, если тест ещё не пройден: нужен только для промпта.
DEFAULT_LEVEL = "A2"

# Порядок критериев в разборе.
CRITERIA: tuple[str, ...] = (
    "task_response",
    "coherence",
    "lexical_resource",
    "grammar",
)

MAX_MESSAGE_LENGTH = 4096
MAX_QUOTE_CHARS = 160
MAX_NOTE_CHARS = 240
MAX_SUMMARY_CHARS = 500

_ZERO_WIDTH = re.compile(r"[\u200b-\u200f\u202a-\u202e\u2060\ufeff]")
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_MULTIPLE_BREAKS = re.compile(r"\n{3,}")


class EssayLengthError(ValueError):
    """Эссе короче 80 или длиннее 500 слов: ИИ не вызывается."""

    def __init__(self, words: int, *, too_short: bool) -> None:
        self.words = words
        self.too_short = too_short
        limit = f"от {MIN_WORDS} до {MAX_WORDS}"
        super().__init__(f"В эссе {words} слов, нужно {limit}")
        self.user_message_key = "essay.too_short" if too_short else "essay.too_long"


@dataclass(frozen=True)
class EssayResult:
    """Сохранённая проверка и готовые сообщения с разбором."""

    essay: Essay
    check: EssayCheck
    band: float
    feedback: list[str]


def clean_essay_text(text: str) -> str:
    """Убирает служебные символы, лишние пробелы и пустые строки."""
    cleaned = _ZERO_WIDTH.sub("", text)
    cleaned = _CONTROL_CHARS.sub("", cleaned)
    cleaned = cleaned.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.strip() for line in cleaned.split("\n")]
    return _MULTIPLE_BREAKS.sub("\n\n", "\n".join(lines)).strip()


def count_words(text: str) -> int:
    """Считает слова по пробелам — так же, как их видит проверяющий."""
    return len(text.split())


def prepare_essay(text: str) -> str:
    """Очищает текст и проверяет длину; возвращает текст для отправки в ИИ."""
    cleaned = clean_essay_text(text)
    words = count_words(cleaned)
    if words < MIN_WORDS:
        raise EssayLengthError(words, too_short=True)
    if words > MAX_WORDS:
        raise EssayLengthError(words, too_short=False)
    return cleaned


def round_band(value: float) -> float:
    """Округляет балл до ближайших 0.5 вверх (6.25 → 6.5, 6.1 → 6.0)."""
    rounded = math.floor(value / BAND_STEP + 0.5) * BAND_STEP
    return round(min(max(rounded, 0.0), 9.0), 1)


def calculate_overall_band(check: EssayCheck) -> float:
    """Общий балл: среднее четырёх критериев, округлённое до 0.5."""
    criteria = check.criteria
    scores = [getattr(criteria, name) for name in CRITERIA]
    return round_band(sum(scores) / len(scores))


def _one_line(value: str, limit: int) -> str:
    """Схлопывает переводы строк и обрезает слишком длинный фрагмент."""
    collapsed = " ".join(value.split())
    if len(collapsed) <= limit:
        return collapsed
    return f"{collapsed[: limit - 1].rstrip()}…"


def escape_fragment(value: str, limit: int = MAX_QUOTE_CHARS) -> str:
    """Готовит фрагмент для сообщения с HTML-разметкой.

    Цитаты берутся из текста пользователя, поэтому `<`, `>` и `&` экранируются:
    эссе с тегами или разметкой не должно ломать сообщение.
    """
    return html.escape(_one_line(value, limit), quote=False)


def format_band(value: float) -> str:
    """Балл в виде 6.0 / 6.5: всегда один знак после точки."""
    return f"{value:.1f}"


def format_essay_feedback(
    check: EssayCheck,
    band: float,
    *,
    lang: str,
) -> list[str]:
    """Собирает разбор эссе; длинный текст режется на сообщения до 4096."""
    criteria = check.criteria
    lines = [t("essay.title", lang, band=format_band(band)), ""]
    lines.extend(
        f"{t(f'essay.criterion.{name}', lang)}: {format_band(getattr(criteria, name))}"
        for name in CRITERIA
    )
    lines.append("")

    weak_spots = check.weak_spots[:MAX_WEAK_SPOTS]
    if weak_spots:
        lines.append(t("essay.weak_title", lang))
        lines.extend(
            t(
                "essay.weak_item",
                lang,
                index=index,
                quote=escape_fragment(spot.quote),
                problem=escape_fragment(spot.problem, MAX_NOTE_CHARS),
                fix=escape_fragment(spot.fix, MAX_NOTE_CHARS),
            )
            for index, spot in enumerate(weak_spots, start=1)
        )
        lines.append("")
    else:
        lines.extend((t("essay.no_weak", lang), ""))

    lines.append(
        t(
            "essay.strengths",
            lang,
            summary=escape_fragment(check.summary, MAX_SUMMARY_CHARS),
        )
    )
    weakest = min(CRITERIA, key=lambda name: getattr(criteria, name))
    lines.append(
        t(
            "essay.main_advice",
            lang,
            criterion=t(f"essay.criterion.{weakest}", lang),
            score=format_band(getattr(criteria, weakest)),
            hint=t(f"essay.hint.{weakest}", lang),
        )
    )
    lines.extend(("", t("essay.disclaimer", lang)))
    return _chunk_lines(lines)


def _chunk_lines(lines: Sequence[str], limit: int = MAX_MESSAGE_LENGTH) -> list[str]:
    """Собирает строки в сообщения не длиннее лимита Telegram."""
    chunks: list[str] = []
    current = ""
    for line in lines:
        candidate = f"{current}\n{line}" if current else line
        if len(candidate) > limit and current:
            chunks.append(current)
            current = line
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks


async def check_essay(
    session: AsyncSession,
    user: User,
    ai: AIClient,
    text: str,
    *,
    now: datetime | None = None,
) -> EssayResult:
    """Проверяет эссе, сохраняет результат и отмечает учебное действие."""
    cleaned = prepare_essay(text)
    level = user.level or DEFAULT_LEVEL
    check = await ai.check_essay(level, user.native_language, cleaned)

    # Общий балл считаем сами: ответ модели может быть несогласован с критериями.
    band = calculate_overall_band(check)
    feedback = format_essay_feedback(check, band, lang=user.native_language)

    score_json = check.model_dump()
    score_json["overall_band"] = band
    essay = await EssayRepo(session).create(
        user_id=user.id,
        text=cleaned,
        score_overall=band,
        score_json=score_json,
        feedback="\n\n".join(feedback),
    )
    await register_activity(session, user.id, "essay", now=as_utc(now))

    logger.info(
        "Эссе: пользователь %s, балл %.1f, слов %d, слабых мест %d",
        user.id,
        band,
        count_words(cleaned),
        len(check.weak_spots),
    )
    return EssayResult(essay=essay, check=check, band=band, feedback=feedback)
