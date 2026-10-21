"""Проверка настроек ИИ: адрес, ключ и модель на реальном запросе.

Запуск из корня проекта (ключ и адрес берутся из окружения или `.env`):
    python -m scripts.check_ai

Скрипт делает три запроса через боевой `AIClient`: обычный текст, JSON-задание
квиза и короткий словарь на сложной модели. Так видно, подходят ли основная и
резервная модели для задач бота, а не только что ключ принят.
"""

import argparse
import asyncio
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bot.config import ConfigError, Settings, get_settings
from bot.logging_setup import setup_logging
from bot.services.ai_client import AIClient
from bot.services.ai_errors import AIError

# Адреса провайдеров, для которых у бота есть готовые пресеты.
NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

NVIDIA_KEY_PREFIX = "nvapi-"
OPENROUTER_KEY_PREFIX = "sk-or-"


def provider_hint(settings: Settings) -> str | None:
    """Подсказка, если ключ и адрес ИИ явно от разных провайдеров."""
    url = settings.ai_server_url.rstrip("/").lower()
    key = settings.ai_api_key.strip()
    if key.startswith(NVIDIA_KEY_PREFIX) and "nvidia" not in url:
        return (
            "ключ от NVIDIA, а AI_SERVER_URL указывает на другого провайдера. "
            f"Для NVIDIA задайте AI_SERVER_URL={NVIDIA_BASE_URL}"
        )
    if key.startswith(OPENROUTER_KEY_PREFIX) and "openrouter" not in url:
        return (
            "ключ от OpenRouter, а AI_SERVER_URL указывает на другого провайдера. "
            f"Для OpenRouter задайте AI_SERVER_URL={OPENROUTER_BASE_URL}"
        )
    return None


async def check_ai(client: AIClient, *, level: str = "A2", lang: str = "ru") -> bool:
    """Проверяет текстовый и JSON-ответ; True — ИИ настроен верно."""
    try:
        answer = await client.free_chat(level, lang, text="Say one short greeting.")
    except AIError as exc:
        print(f"  текст: ошибка — {exc}")
        return False
    print(f"  текст: ok — {answer[:80]!r}")

    try:
        question = await client.generate_quiz(level, lang)
    except AIError as exc:
        print(f"  JSON: ошибка — {exc}")
        return False
    print(f"  JSON: ok — {question.question[:80]!r}")

    try:
        words = await client.generate_vocabulary(level, lang, count=2)
    except AIError as exc:
        print(f"  сложная JSON-задача: ошибка — {exc}")
        return False
    print(f"  сложная JSON-задача: ok — {[word.word for word in words.words]}")
    return True


async def main(level: str, lang: str) -> int:
    """Печатает настройки, гоняет проверки и возвращает код выхода."""
    settings = get_settings()
    print(f"AI_SERVER_URL:     {settings.ai_server_url}")
    print(f"AI_MODEL:          {settings.ai_model}")
    print(f"AI_MODEL_HARD:     {settings.ai_model_hard or settings.ai_model}")
    print(f"AI_MODEL_FALLBACK: {settings.ai_model_fallback or 'не задана'}")
    print(f"AI_API_KEY:        {'задан' if settings.ai_api_key else 'не задан'}")

    hint = provider_hint(settings)
    if hint:
        print(f"ВНИМАНИЕ: {hint}")
    if not settings.ai_api_key:
        print("ВНИМАНИЕ: без AI_API_KEY большинство провайдеров отвечает 401")

    client = AIClient(
        base_url=settings.ai_server_url,
        api_key=settings.ai_api_key,
        model=settings.ai_model,
        hard_model=settings.ai_model_hard or None,
        fallback_model=settings.ai_model_fallback or None,
        timeout=settings.ai_timeout,
    )
    try:
        ok = await check_ai(client, level=level, lang=lang)
    finally:
        await client.close()

    if ok:
        print("Итог: ИИ настроен верно")
        return 0
    print("Итог: ИИ не отвечает — проверьте AI_SERVER_URL, AI_API_KEY и AI_MODEL")
    return 1


if __name__ == "__main__":
    setup_logging()
    parser = argparse.ArgumentParser(description="Проверить настройки ИИ на реальном запросе")
    parser.add_argument("--level", default="A2", help="уровень для тестового запроса")
    parser.add_argument("--lang", default="ru", help="родной язык для тестового запроса")
    arguments = parser.parse_args()
    try:
        raise SystemExit(asyncio.run(main(arguments.level, arguments.lang)))
    except ConfigError as exc:
        print(exc, file=sys.stderr)
        raise SystemExit(1) from exc
