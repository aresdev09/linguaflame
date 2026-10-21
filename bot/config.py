"""Конфигурация приложения.

Все настройки читаются из переменных окружения и файла `.env`
(шаблон — `.env.example`). Токены и ключи в коде не хранятся.
"""

from functools import lru_cache

from pydantic import Field, ValidationError, field_validator, model_validator
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
    # Любой OpenAI-совместимый API. По умолчанию NVIDIA NIM: ключ nvapi-...
    # с https://build.nvidia.com. OpenRouter: https://openrouter.ai/api/v1.
    ai_server_url: str = "https://integrate.api.nvidia.com/v1"
    ai_api_key: str = ""
    ai_model: str = "deepseek-ai/deepseek-v4.1-flash"
    # Таймаут одного запроса: план урока и проверка эссе иногда идут дольше минуты.
    ai_timeout: float = Field(default=180.0, gt=0)
    log_level: str = "INFO"
    # JSON-логи для продакшена; в разработке удобнее обычный текст.
    log_json: bool = False
    # Ограничение расходов на ИИ: логических запросов на пользователя в день.
    # 0 — без ограничения.
    ai_daily_limit: int = Field(default=100, ge=0)
    # Сдвиг часов для ручной проверки напоминаний: 0 — обычное время.
    reminder_hour_offset: int = 0
    # long polling прост в запуске, webhook нужен, если хостинг этого требует.
    bot_mode: str = "polling"
    webhook_base_url: str = ""
    webhook_path: str = "/telegram/webhook"
    webhook_secret: str = ""
    webhook_host: str = "0.0.0.0"
    webhook_port: int = 8080

    @field_validator("bot_mode")
    @classmethod
    def _check_bot_mode(cls, value: str) -> str:
        mode = value.strip().lower()
        if mode not in ("polling", "webhook"):
            raise ValueError("допустимо только polling или webhook")
        return mode

    @model_validator(mode="after")
    def _check_webhook_settings(self) -> "Settings":
        if self.bot_mode == "webhook" and not self.webhook_base_url.strip():
            raise ValueError("для webhook нужен WEBHOOK_BASE_URL")
        return self

    @property
    def webhook_url(self) -> str:
        """Полный адрес webhook: базовый URL плюс путь."""
        return f"{self.webhook_base_url.rstrip('/')}{self.webhook_path}"


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
