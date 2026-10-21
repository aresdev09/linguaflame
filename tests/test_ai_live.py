"""Проверка реального NVIDIA API на настройках по умолчанию.

Тест обращается к внешнему сервису и расходует токены, поэтому по умолчанию
пропускается. Запуск из корня проекта:

    RUN_LIVE_AI=1 pytest -q tests/test_ai_live.py
"""

import os

import pytest

from bot.config import Settings, get_settings
from bot.services.ai_client import AIClient

LIVE_AI_ENABLED = os.getenv("RUN_LIVE_AI") == "1"


@pytest.mark.skipif(not LIVE_AI_ENABLED, reason="set RUN_LIVE_AI=1 to call the real API")
async def test_default_nvidia_settings_can_complete_requests() -> None:
    """С настройками по умолчанию API отвечает и на текст, и на JSON."""
    configured = get_settings()
    if not configured.ai_api_key:
        pytest.skip("AI_API_KEY is not configured")

    settings = Settings(
        _env_file=None,
        bot_token="live-api-test",
        ai_api_key=configured.ai_api_key,
    )
    client = AIClient(
        base_url=settings.ai_server_url,
        api_key=settings.ai_api_key,
        model=settings.ai_model,
        hard_model=settings.ai_model_hard or None,
        fallback_model=settings.ai_model_fallback or None,
        timeout=settings.ai_timeout,
    )
    try:
        answer = await client.free_chat("A2", "ru", text="Say one short greeting.")
        assert answer.strip()

        question = await client.generate_quiz("A2", "ru")
        assert question.options
        assert question.correct in question.options

        plan = await client.generate_lesson_plan("A2", "ru")
        assert plan.steps
        assert len(plan.final_test) == 5
    finally:
        await client.close()
