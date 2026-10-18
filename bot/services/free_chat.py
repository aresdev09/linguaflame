"""Свободный разговор с ботом на любом языке.

Правила:
- ответ приходит обычным текстом, а не JSON;
- история диалога хранится в FSM: только последние 10 сообщений;
- текст ученика уходит в ИИ в тегах `<user_text>` как данные;
- ошибки в английском модель исправляет мягко из `FREE_CHAT_RULES`.

Здесь нет aiogram-импортов: историю передают хендлеры, сервис её чистит
и режет до `HISTORY_LIMIT`.
"""

from collections.abc import Iterable
from datetime import datetime, time, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from bot.models import User
from bot.repositories import ActivityRepo
from bot.services.ai_client import AIClient
from bot.services.streak import register_activity
from bot.services.timezones import as_utc, resolve_timezone

# Сколько последних сообщений диалога (вопрос + ответ) держим в FSM.
HISTORY_LIMIT = 10

# Уровень по умолчанию, если тест ещё не пройден: нужен только для промпта.
DEFAULT_LEVEL = "A2"

# Роли, которые допускаются в истории: system подставляет сам клиент.
HISTORY_ROLES: frozenset[str] = frozenset(("user", "assistant"))

HISTORY_KEY = "history"


def command_name(text: str | None) -> str | None:
    """Имя команды из сообщения `/quiz@bot` → `quiz`; не команда — None."""
    if not text or not text.startswith("/"):
        return None
    token = text.split(maxsplit=1)[0][1:]
    name = token.split("@", 1)[0].strip().lower()
    return name or None


def trim_history(
    raw: Iterable[object] | object,
    *,
    limit: int = HISTORY_LIMIT,
) -> list[dict[str, str]]:
    """Оставляет последние `limit` корректных сообщений истории.

    Данные из FSM могут быть испорчены (старая версия, ручная правка),
    поэтому некорректные элементы отбрасываются, а не ломают запрос.
    """
    if not isinstance(raw, (list, tuple)):
        return []
    items: list[dict[str, str]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        role = item.get("role")
        content = item.get("content")
        if role not in HISTORY_ROLES or not isinstance(content, str):
            continue
        text = content.strip()
        if text:
            items.append({"role": role, "content": text})
    return items[-limit:]


def append_exchange(
    history: Iterable[object] | object,
    user_text: str,
    answer: str,
    *,
    limit: int = HISTORY_LIMIT,
) -> list[dict[str, str]]:
    """Добавляет реплики в историю и обрезает её до последних `limit`."""
    return trim_history(
        [
            *trim_history(history),
            {"role": "user", "content": user_text},
            {"role": "assistant", "content": answer},
        ],
        limit=limit,
    )


async def reply_in_chat(
    session: AsyncSession,
    user: User,
    ai: AIClient,
    text: str,
    *,
    history: Iterable[object] | object = (),
    now: datetime | None = None,
) -> str:
    """Ответ на сообщение с учётом истории; отмечает активность за день.

    `register_activity` вызывается один раз в календарный день пользователя:
    в лог чата за день попадает одна запись, серия при этом растёт как обычно.
    """
    answer = (
        await ai.free_chat(
            user.level or DEFAULT_LEVEL,
            user.native_language,
            history=trim_history(history),
            text=text,
        )
    ).strip()
    await _register_chat_activity(session, user, now=now)
    return answer


async def _register_chat_activity(
    session: AsyncSession,
    user: User,
    *,
    now: datetime | None = None,
) -> bool:
    """Пишет активность чата, если сегодня её ещё не было. True — записали."""
    moment = as_utc(now)
    timezone_info = resolve_timezone(user.timezone, user_id=user.id)
    day_start = datetime.combine(
        moment.astimezone(timezone_info).date(),
        time.min,
        tzinfo=timezone_info,
    ).astimezone(timezone.utc)

    activities = ActivityRepo(session)
    if await activities.has_since(user.id, "chat", day_start):
        return False

    await register_activity(session, user.id, "chat", now=moment)
    return True
