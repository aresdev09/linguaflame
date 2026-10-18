"""Тесты локализации."""

import pytest

from bot.locales import DEFAULT_LANGUAGE, SUPPORTED_LANGUAGES, en, ru, t


def test_ru_and_en_have_the_same_keys() -> None:
    assert set(ru.TEXTS) == set(en.TEXTS)
    assert "ru" in SUPPORTED_LANGUAGES
    assert "en" in SUPPORTED_LANGUAGES


def test_t_returns_text_of_requested_language() -> None:
    assert t("start.greeting", "ru", name="Аня") == ("Привет, Аня! Я бот для изучения английского.")
    assert t("start.greeting", "en", name="Anna") == ("Hi, Anna! I am a bot for learning English.")


def test_t_falls_back_to_default_language() -> None:
    assert DEFAULT_LANGUAGE == "ru"
    assert t("start.greeting", "de", name="Hans") == ru.TEXTS["start.greeting"].format(name="Hans")
    assert t("start.greeting", None, name="X") == ru.TEXTS["start.greeting"].format(name="X")


def test_t_formats_placeholders() -> None:
    assert "Asia/Samarkand" in t("start.timezone_saved", "ru", timezone="Asia/Samarkand")


def test_t_raises_for_unknown_key() -> None:
    with pytest.raises(KeyError):
        t("no.such.key", "ru")
