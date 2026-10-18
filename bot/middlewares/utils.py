"""Вспомогательные функции middleware."""

from typing import Any


def telegram_user_from(event: Any, data: dict[str, Any]) -> Any | None:
    """Telegram-пользователь апдейта или None.

    Middleware висят на `dp.update`, поэтому `event` — это `Update`,
    а не конкретное событие: у `Update` нет `from_user`. Пользователь
    уже разобран и лежит в `data["event_from_user"]`.
    """
    user = data.get("event_from_user")
    if user is not None:
        return user
    source = getattr(event, "event", event)
    return getattr(source, "from_user", None)