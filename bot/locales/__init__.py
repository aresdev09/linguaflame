"""Локализация бота: тексты по ключам, языки ru и en.

Все строки, которые видит пользователь, берутся отсюда через `t(key, lang)`.
"""

from typing import Final

from bot.locales import en, ru

DEFAULT_LANGUAGE: Final[str] = "ru"
SUPPORTED_LANGUAGES: Final[tuple[str, ...]] = ("ru", "en")

_TEXTS: Final[dict[str, dict[str, str]]] = {"ru": ru.TEXTS, "en": en.TEXTS}


def t(key: str, lang: str | None = None, **kwargs: object) -> str:
    """Текст по ключу для языка пользователя.

    Неизвестный или пустой язык и отсутствие ключа в языке — откат на русский.
    Ключа нет ни в одном языке — KeyError, его перехватит ErrorMiddleware.
    """
    texts = _TEXTS.get(lang or "", ru.TEXTS)
    text = texts.get(key)
    if text is None:
        text = ru.TEXTS.get(key)
    if text is None:
        raise KeyError(f"Нет текста для ключа {key!r}")
    return text.format(**kwargs) if kwargs else text
