"""Единая настройка логирования проекта.

Текстовый формат удобен в разработке, JSON (`LOG_JSON=true`) — в продакшене:
строки можно собирать и искать по полям (level, logger, user_id и т.д.).
"""

import json
import logging
from datetime import datetime, timezone

LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Библиотеки, чьи INFO-сообщения слишком шумные для продакшена.
NOISY_LOGGERS: tuple[str, ...] = ("httpx", "httpcore", "aiogram.event")

# Стандартные поля LogRecord: остальные считаются добавленными через `extra`.
_RESERVED_FIELDS = frozenset(
    {
        "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
        "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
        "created", "msecs", "relativeCreated", "thread", "threadName",
        "processName", "process", "taskName", "message", "asctime",
    }
)


class JsonFormatter(logging.Formatter):
    """Структурная строка лога: время, уровень, логгер, сообщение и extra."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "ts": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key in _RESERVED_FIELDS or key.startswith("_"):
                continue
            payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def setup_logging(level: str = "INFO", *, json_logs: bool = False) -> None:
    """Настраивает корневой логгер: уровень, форматер и тихие библиотеки."""
    numeric_level = getattr(logging, str(level).upper(), None)
    if not isinstance(numeric_level, int):
        numeric_level = logging.INFO

    formatter: logging.Formatter
    if json_logs:
        formatter = JsonFormatter()
    else:
        formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    logging.basicConfig(
        level=numeric_level,
        handlers=[handler],
        force=True,
    )

    for name in NOISY_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)
