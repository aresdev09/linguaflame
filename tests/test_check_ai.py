"""Тесты проверки настроек ИИ (`python -m scripts.check_ai`)."""

import pytest

from bot.config import Settings
from bot.services.ai_errors import AIRequestRejected
from bot.services.fake_ai_client import FakeAIClient
from scripts.check_ai import NVIDIA_BASE_URL, OPENROUTER_BASE_URL, check_ai, provider_hint


def _settings(**overrides: str) -> Settings:
    values = {
        "bot_token": "123:TEST",
        "ai_api_key": "",
        "ai_server_url": OPENROUTER_BASE_URL,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


async def test_check_ai_passes_with_working_client() -> None:
    assert await check_ai(FakeAIClient()) is True


async def test_check_ai_fails_on_text_request() -> None:
    client = FakeAIClient(error=AIRequestRejected("401 Unauthorized"))

    assert await check_ai(client) is False
    assert len(client.calls) == 1  # после ошибки текста JSON-запрос не нужен


async def test_check_ai_fails_on_invalid_json_answer() -> None:
    client = FakeAIClient()

    async def broken_quiz(level: str, lang: str):
        client._record("quiz", level=level, lang=lang)
        raise AIRequestRejected("ответ не JSON")

    client.generate_quiz = broken_quiz  # type: ignore[method-assign]

    assert await check_ai(client) is False


def test_hint_for_nvidia_key_on_openrouter_url() -> None:
    hint = provider_hint(_settings(ai_api_key="nvapi-test", ai_server_url=OPENROUTER_BASE_URL))

    assert hint is not None
    assert NVIDIA_BASE_URL in hint


def test_hint_for_openrouter_key_on_nvidia_url() -> None:
    hint = provider_hint(_settings(ai_api_key="sk-or-test", ai_server_url=NVIDIA_BASE_URL))

    assert hint is not None
    assert OPENROUTER_BASE_URL in hint


@pytest.mark.parametrize(
    ("key", "url"),
    [
        ("nvapi-test", NVIDIA_BASE_URL),
        ("sk-or-test", OPENROUTER_BASE_URL),
        ("", NVIDIA_BASE_URL),
    ],
)
def test_no_hint_when_provider_matches(key: str, url: str) -> None:
    assert provider_hint(_settings(ai_api_key=key, ai_server_url=url)) is None
