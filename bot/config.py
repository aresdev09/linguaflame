"""Конфигурация приложения.

Все настройки читаются из переменных окружения и файла `.env`
(шаблон — `.env.example`). Токены и ключи в коде не хранятся.
"""

from functools import lru_cache

from pydantic import Field, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_DATABASE_URL = "sqlite+aiosqlite:///./linguflame.db"

# --- Тест уровня ---
# Уровни CEFR по возрастанию.
LEVELS: tuple[str, ...] = ("A1", "A2", "B1", "B2", "C1", "C2")
# Вес правильного ответа по уровню вопроса.
LEVEL_WEIGHTS: dict[str, float] = {
    "A1": 1.0,
    "A2": 2.0,
    "B1": 3.0,
    "B2": 4.0,
    "C1": 5.0,
    "C2": 6.0,
}
# Сколько вопросов каждого уровня попадает в тест (в сумме 50).
LEVEL_TEST_DISTRIBUTION: dict[str, int] = {
    "A1": 8,
    "A2": 8,
    "B1": 8,
    "B2": 8,
    "C1": 8,
    "C2": 10,
}
# Нижние пороги итогового процента: [0, 15) A1, [15, 30) A2, [30, 50) B1,
# [50, 70) B2, [70, 88) C1, [88, 100] C2.
LEVEL_THRESHOLDS: tuple[tuple[float, str], ...] = (
    (0.0, "A1"),
    (15.0, "A2"),
    (30.0, "B1"),
    (50.0, "B2"),
    (70.0, "C1"),
    (88.0, "C2"),
)
# Норма времени на вопрос по уровню: быстрее неё — бонус к баллу.
LEVEL_SPEED_NORMS_SEC: dict[str, int] = {
    "A1": 20,
    "A2": 18,
    "B1": 15,
    "B2": 12,
    "C1": 10,
    "C2": 10,
}
# Максимальный бонус за скорость (+10% к весу вопроса).
SPEED_BONUS: float = 0.10
# Вопрос B1 и выше, отвеченный быстрее 2 секунд, считается угадыванием.
SPEED_GUESSING_SEC: int = 2
# Ответ дольше 60 секунд бонуса не получает.
SPEED_SLOW_SEC: int = 60
# Проверка согласованности: уровень с точностью не ниже 60% может поднять итог.
CONSISTENCY_MIN_ACCURACY: float = 0.60


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
    ai_server_url: str = "https://openrouter.ai/api/v1"
    ai_api_key: str = ""
    ai_model: str = "nvidia/nemotron-3.5-super-vl:free"
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
