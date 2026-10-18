"""Ошибки AI-клиента.

`user_message_key` — ключ локализации с понятным текстом для пользователя,
поэтому Telegram-слой показывает его, а не техническое сообщение.
"""


class AIError(RuntimeError):
    """Базовая ошибка общения с AI-сервером."""

    user_message_key = "common.ai_unavailable"


class AIRequestError(AIError):
    """Сеть, таймаут или ответ 5xx — запрос повторяется."""

    user_message_key = "common.ai_unavailable"


class AITimeoutError(AIRequestError):
    """Модель не ответила за отведённое время: повтор только удлинит ожидание."""

    user_message_key = "common.ai_unavailable"


class AIResponseError(AIError):
    """Ответ не разобрался или не прошёл схему — запрос повторяется."""

    user_message_key = "common.ai_bad_answer"


class AIRequestRejected(AIError):
    """Сервер отверг запрос (4xx) — повтор не поможет."""

    user_message_key = "common.ai_unavailable"


class AIQuotaExceeded(AIError):
    """Дневной лимит запросов к ИИ исчерпан."""

    user_message_key = "common.ai_limit"