"""Тесты конфигурации."""

import pytest
from pydantic import ValidationError

from bot.config import ConfigError, Settings, get_settings

ENV_VARS = (
    "BOT_TOKEN",
    "DATABASE_URL",
    "REDIS_URL",
    "AI_SERVER_URL",
    "AI_API_KEY",
    "AI_MODEL",
    "AI_TIMEOUT",
    "LOG_LEVEL",
)


def _clear_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in ENV_VARS:
        monkeypatch.delenv(var, raising=False)


def test_settings_load_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_env(monkeypatch)
    monkeypatch.setenv("BOT_TOKEN", "123456:TEST-TOKEN")

    settings = Settings(_env_file=None)

    assert settings.bot_token == "123456:TEST-TOKEN"
    assert settings.database_url.startswith("sqlite+aiosqlite")
    assert settings.redis_url.startswith("redis://")
    assert settings.log_level == "INFO"


def test_ai_defaults_target_nvidia(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_env(monkeypatch)
    monkeypatch.setenv("BOT_TOKEN", "123456:TEST-TOKEN")

    settings = Settings(_env_file=None)

    assert settings.ai_server_url == "https://integrate.api.nvidia.com/v1"
    assert settings.ai_model == "nvidia/nemotron-3-ultra-550b-a55b"
    assert settings.ai_timeout == 180.0


def test_settings_require_bot_token(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_env(monkeypatch)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_settings_reject_empty_bot_token(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_env(monkeypatch)
    monkeypatch.setenv("BOT_TOKEN", "")

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_get_settings_has_clear_error(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    _clear_env(monkeypatch)
    monkeypatch.chdir(tmp_path)
    get_settings.cache_clear()
    try:
        with pytest.raises(ConfigError) as exc_info:
            get_settings()
    finally:
        get_settings.cache_clear()

    message = str(exc_info.value)
    assert "BOT_TOKEN" in message
    assert ".env" in message


def test_main_module_imports() -> None:
    import bot.main  # noqa: F401
