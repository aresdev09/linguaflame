"""Часовые пояса пользователей: все пересчёты через zoneinfo."""

import logging
from datetime import UTC, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

logger = logging.getLogger(__name__)

DEFAULT_TIMEZONE = "UTC"


def resolve_timezone(name: str | None, *, user_id: int | None = None) -> ZoneInfo:
    """ZoneInfo по имени из `users.timezone`.

    Неизвестное или пустое имя — UTC, с предупреждением в лог.
    """
    candidate = (name or "").strip() or DEFAULT_TIMEZONE
    try:
        return ZoneInfo(candidate)
    except (ZoneInfoNotFoundError, ValueError):
        logger.warning(
            "Неизвестный часовой пояс %r (пользователь %s), использую %s",
            name,
            user_id,
            DEFAULT_TIMEZONE,
        )
        return ZoneInfo(DEFAULT_TIMEZONE)


def as_utc(moment: datetime | None = None) -> datetime:
    """Приводит момент к aware UTC; без момента — текущее время."""
    if moment is None:
        return datetime.now(UTC)
    if moment.tzinfo is None:
        return moment.replace(tzinfo=UTC)
    return moment.astimezone(UTC)
