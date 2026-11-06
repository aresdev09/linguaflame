"""Тесты локализации."""

from string import Formatter

import pytest

from bot.locales import DEFAULT_LANGUAGE, SUPPORTED_LANGUAGES, en, ru, t, uz

_LOCALES = {"ru": ru.TEXTS, "en": en.TEXTS, "uz": uz.TEXTS}


def test_all_supported_languages_have_texts() -> None:
    assert set(_LOCALES) == set(SUPPORTED_LANGUAGES)
    assert "ru" in SUPPORTED_LANGUAGES
    assert "en" in SUPPORTED_LANGUAGES
    assert "uz" in SUPPORTED_LANGUAGES


def test_all_locales_have_the_same_keys() -> None:
    reference = set(ru.TEXTS)
    for lang, texts in _LOCALES.items():
        assert set(texts) == reference, lang


def test_all_locales_have_the_same_placeholders() -> None:
    def placeholders(template: str) -> set[str]:
        return {field for _, field, _, _ in Formatter().parse(template) if field}

    for key, template in ru.TEXTS.items():
        expected = placeholders(template)
        for lang, texts in _LOCALES.items():
            assert placeholders(texts[key]) == expected, (lang, key)


def test_language_names_exist_for_every_supported_language() -> None:
    for code in SUPPORTED_LANGUAGES:
        assert t(f"language.{code}", "ru")


def test_t_returns_text_of_requested_language() -> None:
    assert t("start.greeting", "ru", name="Аня") == ("Привет, Аня! Я бот для изучения английского.")
    assert t("start.greeting", "en", name="Anna") == ("Hi, Anna! I am a bot for learning English.")
    assert t("start.greeting", "uz", name="Aziza") == (
        "Salom, Aziza! Men ingliz tilini o'rganishga yordam beradigan botman."
    )


def test_t_falls_back_to_default_language() -> None:
    assert DEFAULT_LANGUAGE == "ru"
    assert t("start.greeting", "de", name="Hans") == ru.TEXTS["start.greeting"].format(name="Hans")
    assert t("start.greeting", None, name="X") == ru.TEXTS["start.greeting"].format(name="X")


def test_t_formats_placeholders() -> None:
    assert "Asia/Samarkand" in t("start.timezone_saved", "ru", timezone="Asia/Samarkand")
    assert "Asia/Samarkand" in t("start.timezone_saved", "uz", timezone="Asia/Samarkand")


def test_t_raises_for_unknown_key() -> None:
    with pytest.raises(KeyError):
        t("no.such.key", "ru")
