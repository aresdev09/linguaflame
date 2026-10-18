"""Тесты структурных логов и уровней."""

import json
import logging

from bot.logging_setup import JsonFormatter, NOISY_LOGGERS, setup_logging


def _record(level: int = logging.INFO) -> logging.LogRecord:
    return logging.LogRecord(
        name="bot.test",
        level=level,
        pathname=__file__,
        lineno=1,
        msg="Привет, %s",
        args=("мир",),
        exc_info=None,
    )


def test_json_formatter_has_required_fields() -> None:
    payload = json.loads(JsonFormatter().format(_record()))

    assert payload["level"] == "INFO"
    assert payload["logger"] == "bot.test"
    assert payload["message"] == "Привет, мир"
    assert "ts" in payload


def test_json_formatter_includes_extra_fields() -> None:
    record = _record()
    record.user_id = 42
    record.event = "quiz"

    payload = json.loads(JsonFormatter().format(record))

    assert payload["user_id"] == 42
    assert payload["event"] == "quiz"


def test_json_formatter_includes_exception() -> None:
    try:
        raise RuntimeError("boom")
    except RuntimeError:
        import sys

        record = logging.LogRecord(
            name="bot.test",
            level=logging.ERROR,
            pathname=__file__,
            lineno=1,
            msg="Ошибка",
            args=(),
            exc_info=sys.exc_info(),
        )

    payload = json.loads(JsonFormatter().format(record))

    assert payload["level"] == "ERROR"
    assert "RuntimeError: boom" in payload["exception"]


def test_setup_logging_levels_and_json_handler() -> None:
    setup_logging("DEBUG", json_logs=True)
    try:
        handler = logging.getLogger().handlers[0]
        assert logging.getLogger().level == logging.DEBUG
        assert isinstance(handler.formatter, JsonFormatter)
        for name in NOISY_LOGGERS:
            assert logging.getLogger(name).level == logging.WARNING
    finally:
        setup_logging("INFO")


def test_setup_logging_text_handler() -> None:
    setup_logging("WARNING")
    try:
        handler = logging.getLogger().handlers[0]
        assert not isinstance(handler.formatter, JsonFormatter)
        assert logging.getLogger().level == logging.WARNING
    finally:
        setup_logging("INFO")


def test_unknown_level_falls_back_to_info() -> None:
    setup_logging("not-a-level")
    try:
        assert logging.getLogger().level == logging.INFO
    finally:
        setup_logging("INFO")
