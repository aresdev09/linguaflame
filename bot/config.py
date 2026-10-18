"""Конфигурация приложения.

Все настройки читаются из переменных окружения и файла `.env`
(шаблон — `.env.example`). Токены и ключи в коде не хранятся.
"""

from functools import lru_cache

from pydantic import Field, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_DATABASE_URL = "sqlite+aiosqlite:///./linguflame.db"


class ConfigError(RuntimeError):
    """Понятная ошибка конфигурации, показывается пользователю при запуске."""


class Settings(BaseSettings):
    """Настройки приложения из окружения и `.env`."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    bot_token: str = Field(min_length=1)
    database_url: str = DEFAULT_DATABASE_URL
    redis_url: str = "redis://localhost:6379/0"
    ai_server_url: str = "http://localhost:8000"
    ai_api_key: str = ""
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    """Возвращает настройки или поднимает ConfigError с понятным текстом."""
    try:
        return Settings()
    except ValidationError as exc:
        problems = []
        for error in exc.errors():
            field = str(error["loc"][0]).upper() if error["loc"] else "?"
            if error["type"] == "missing":
                reason = "переменная не задана"
            elif error["type"] == "string_too_short":
                reason = "пустое значение"
            else:
                reason = error["msg"]
            problems.append(f"- {field}: {reason}")
        details = "\n".join(problems)
        raise ConfigError(
            "Не удалось загрузить настройки из окружения:\n"
            f"{details}\n"
            "Скопируйте .env.example в .env и заполните значения "
            "(или задайте переменные окружения)."
        ) from exc
