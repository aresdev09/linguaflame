"""Ежедневный набор слов: генерация, проверка, сохранение и повторная выдача.

Правила:
- ровно 20 слов, у каждого слово, транскрипция и перевод на родной язык;
- слова из последних 7 дней не повторяются;
- набор сохраняется в `vocabulary_sets`; повторный вызов в тот же день
  возвращает сохранённый набор без запроса к ИИ;
- каждое обращение к словам дня — учебное действие (растёт серия).
"""

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from bot.locales import t
from bot.prompts import tasks
from bot.repositories import UserRepo, VocabularyRepo
from bot.services.ai_client import AIClient
from bot.services.ai_errors import AIResponseError
from bot.services.ai_schemas import Word
from bot.services.streak import register_activity
from bot.services.timezones import as_utc, resolve_timezone

logger = logging.getLogger(__name__)

WORDS_PER_DAY = tasks.WORDS_PER_DAY
DEFAULT_LEVEL = "A2"
EXCLUDE_DAYS = 7
MAX_GENERATION_ATTEMPTS = 3
MAX_MESSAGE_LENGTH = 4096


@dataclass(frozen=True)
class DailyVocabulary:
    """Набор слов на день вместе с контекстом выдачи."""

    words: list[Word]
    level: str
    level_default: bool
    reused: bool


async def get_daily_vocabulary(
    session: AsyncSession,
    user_id: int,
    ai: AIClient,
    *,
    now: datetime | None = None,
) -> DailyVocabulary:
    """Возвращает набор слов на сегодня, при необходимости генерируя новый."""
    user = await UserRepo(session).get(user_id)
    if user is None:
        raise ValueError(f"Пользователь {user_id} не найден")

    moment = as_utc(now)
    timezone_info = resolve_timezone(user.timezone, user_id=user_id)
    today = moment.astimezone(timezone_info).date()

    repo = VocabularyRepo(session)
    level_default = not user.level
    level = user.level or DEFAULT_LEVEL

    saved = await repo.get_by_date(user_id, today)
    if saved is not None:
        words = [Word.model_validate(item) for item in saved.words]
        logger.info("Слова дня: пользователь %s, сохранённый набор", user_id)
        await register_activity(session, user_id, "vocabulary", now=moment)
        return DailyVocabulary(
            words=words,
            level=level,
            level_default=level_default,
            reused=True,
        )

    recent = await repo.recent_words(user_id, today - timedelta(days=EXCLUDE_DAYS - 1))
    words = await _generate_words(ai, level, user.native_language, recent)

    await repo.save(user_id, today, [word.model_dump() for word in words])
    await register_activity(session, user_id, "vocabulary", now=moment)
    logger.info(
        "Слова дня: пользователь %s, новый набор (%d слов, уровень %s)",
        user_id,
        len(words),
        level,
    )
    return DailyVocabulary(
        words=words,
        level=level,
        level_default=level_default,
        reused=False,
    )


async def _generate_words(
    ai: AIClient,
    level: str,
    lang: str,
    exclude_words: Sequence[str],
) -> list[Word]:
    """Запрашивает слова, добирая недостающие и не повторяя уже выданные."""
    collected: list[Word] = []
    excluded = {word.casefold() for word in exclude_words}
    attempts = 0

    while len(collected) < WORDS_PER_DAY and attempts < MAX_GENERATION_ATTEMPTS:
        needed = WORDS_PER_DAY - len(collected)
        response = await ai.generate_vocabulary(
            level,
            lang,
            count=needed,
            exclude_words=sorted(excluded),
        )
        attempts += 1
        for word in response.words:
            key = word.word.casefold()
            if key in excluded:
                continue
            excluded.add(key)
            collected.append(word)
            if len(collected) == WORDS_PER_DAY:
                break

    if len(collected) < WORDS_PER_DAY:
        raise AIResponseError(f"ИИ вернул {len(collected)} слов вместо {WORDS_PER_DAY}")
    return collected


def format_daily_vocabulary(daily: DailyVocabulary, lang: str) -> list[str]:
    """Готовые сообщения со словами; длинный список режется по 4096 символов."""
    lines = [t("vocabulary.title", lang, level=daily.level)]
    if daily.reused:
        lines.append(t("vocabulary.reused", lang))
    if daily.level_default:
        lines.append(t("vocabulary.default_level", lang, level=daily.level))
    lines.append("")
    lines.extend(
        t(
            "vocabulary.item",
            lang,
            index=index,
            word=word.word,
            transcription=format_transcription(word.transcription),
            translation=word.translation,
        )
        for index, word in enumerate(daily.words, start=1)
    )
    return _chunk_lines(lines)


def format_transcription(value: str) -> str:
    """Приводит транскрипцию к виду /.../."""
    cleaned = value.strip()
    if cleaned.startswith("/") and cleaned.endswith("/") and len(cleaned) > 1:
        return cleaned
    return f"/{cleaned.strip('/')}/"


def _chunk_lines(lines: Sequence[str], limit: int = MAX_MESSAGE_LENGTH) -> list[str]:
    """Собирает строки в сообщения не длиннее limit."""
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
