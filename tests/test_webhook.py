"""Тесты выбора режима polling/webhook."""

import pytest
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from pydantic import ValidationError

from bot.config import Settings
from bot.webhook import build_webhook_app


def _settings(**overrides: object) -> Settings:
    payload: dict[str, object] = {"bot_token": "123:TEST", "_env_file": None}
    payload.update(overrides)
    return Settings(**payload)


def test_polling_is_default_mode() -> None:
    assert _settings().bot_mode == "polling"


def test_webhook_mode_builds_public_url() -> None:
    settings = _settings(
        bot_mode="webhook",
        webhook_base_url="https://bot.example.com/",
        webhook_path="/telegram/webhook",
    )

    assert settings.webhook_url == "https://bot.example.com/telegram/webhook"


def test_webhook_mode_requires_base_url() -> None:
    with pytest.raises(ValidationError):
        _settings(bot_mode="webhook")


def test_unknown_mode_is_rejected() -> None:
    with pytest.raises(ValidationError):
        _settings(bot_mode="carrier-pigeon")


async def test_webhook_app_registers_path() -> None:
    settings = _settings(
        bot_mode="webhook",
        webhook_base_url="https://bot.example.com",
    )
    bot = Bot(token="123:TEST")
    dispatcher = Dispatcher(storage=MemoryStorage())
    try:
        app = build_webhook_app(bot, dispatcher, settings)
        paths = {
            route.resource.canonical
            for route in app.router.routes()
            if route.resource is not None
        }
    finally:
        await bot.session.close()

    assert "/telegram/webhook" in paths
