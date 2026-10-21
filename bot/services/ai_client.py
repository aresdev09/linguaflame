"""Единый клиент общения с ИИ через OpenAI-совместимый API.

Провайдер задаётся настройками: OpenRouter, NVIDIA NIM
(https://integrate.api.nvidia.com/v1) или любой другой совместимый сервер.

Весь код бота ходит в ИИ только через этот класс.

Контракт запроса:
    POST {AI_SERVER_URL}/chat/completions   # по умолчанию https://integrate.api.nvidia.com/v1
    headers: Authorization: Bearer <AI_API_KEY>, Content-Type: application/json

    body:
        {
            "model": "<AI_MODEL>",
            "messages": [
                {"role": "system", "content": "..."},
                {"role": "user", "content": "..."}
            ]
        }

Ответ — стандартный ответ OpenAI-совместимого API: результат лежит строкой в
`choices[0].message.content` (для задач с JSON — JSON, возможно в markdown-обёртке),
а `usage.prompt_tokens` / `usage.completion_tokens` показывают расход токенов.
Адрес, ключ и модель берутся только из конфига.
"""

import asyncio
import json
import logging
import re
import time
from collections.abc import Awaitable, Callable, Iterable, Sequence
from functools import lru_cache
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from bot.config import get_settings
from bot.prompts import tasks
from bot.prompts.base import build_system_prompt, wrap_user_text
from bot.services.ai_errors import (
    AIError,
    AIRequestError,
    AIRequestRejected,
    AIResponseError,
    AITimeoutError,
)
from bot.services.ai_schemas import (
    EssayCheck,
    LessonPlan,
    QuizQuestion,
    VocabularyResponse,
)

logger = logging.getLogger(__name__)

SchemaT = TypeVar("SchemaT", bound=BaseModel)

CHAT_COMPLETIONS_PATH = "/chat/completions"
# Бесплатные reasoning-модели отвечают 20–40 с, поэтому запас больше типичного.
DEFAULT_TIMEOUT = 60.0
MAX_RETRIES = 2
RETRY_BASE_DELAY = 1.0
CHARS_PER_TOKEN = 4  # грубая оценка, если сервер не вернул usage
RATE_LIMIT_STATUS = 429  # у бесплатных моделей это обычное дело, поэтому повторяем

BOT_TITLE_HEADER = "X-Title"  # необязательный заголовок OpenRouter; другие API его игнорируют


def strip_markdown_fences(text: str) -> str:
    """Убирает обёртку ```json ... ``` вокруг ответа модели."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z0-9_+-]*[ \t]*", "", cleaned)
        cleaned = re.sub(r"[ \t]*```$", "", cleaned)
    return cleaned.strip()


def parse_json_payload(text: str) -> Any:
    """Разбирает JSON: снимает markdown, иначе ищет сам объект в тексте."""
    cleaned = strip_markdown_fences(text)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start == -1 or end <= start:
            raise
        return json.loads(cleaned[start : end + 1])


class AIClient:
    """Надёжная обёртка над OpenAI-совместимым API: таймаут, повторы, валидация JSON."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        *,
        model: str,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = MAX_RETRIES,
        retry_delay: float = RETRY_BASE_DELAY,
        client: httpx.AsyncClient | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._sleep = sleep
        self._client = client or httpx.AsyncClient(timeout=timeout)
        self._owns_client = client is None

    async def close(self) -> None:
        """Закрывает httpx-клиент, если он создан самим AIClient."""
        if self._owns_client:
            await self._client.aclose()

    # --- задачи бота ---------------------------------------------------

    async def generate_quiz(self, level: str, lang: str) -> QuizQuestion:
        """Один вопрос квиза под уровень пользователя."""
        return await self._request_json(
            QuizQuestion,
            task="quiz",
            level=level,
            lang=lang,
            prompt=tasks.quiz_prompt(),
        )

    async def generate_vocabulary(
        self,
        level: str,
        lang: str,
        *,
        count: int = tasks.WORDS_PER_DAY,
        exclude_words: Iterable[str] = (),
    ) -> VocabularyResponse:
        """Набор слов за день, без слов из exclude_words."""
        return await self._request_json(
            VocabularyResponse,
            task="vocabulary",
            level=level,
            lang=lang,
            prompt=tasks.vocabulary_prompt(count, exclude_words),
        )

    async def generate_lesson_plan(
        self,
        level: str,
        lang: str,
        *,
        topic: str | None = None,
    ) -> LessonPlan:
        """План урока по грамматике."""
        return await self._request_json(
            LessonPlan,
            task="lesson_plan",
            level=level,
            lang=lang,
            prompt=tasks.lesson_plan_prompt(topic),
        )

    async def check_essay(self, level: str, lang: str, text: str) -> EssayCheck:
        """Проверка эссе по четырём критериям IELTS."""
        return await self._request_json(
            EssayCheck,
            task="essay_check",
            level=level,
            lang=lang,
            prompt=tasks.essay_prompt(wrap_user_text(text)),
            with_user_text=True,
        )

    async def free_chat(
        self,
        level: str,
        lang: str,
        *,
        history: Sequence[dict[str, str]] = (),
        text: str,
    ) -> str:
        """Свободный разговор: обычный текст вместо JSON."""
        return await self._request_text(
            task="free_chat",
            level=level,
            lang=lang,
            prompt=wrap_user_text(text),
            history=history,
            with_user_text=True,
            extra=tasks.FREE_CHAT_RULES,
        )

    async def ask_in_lesson(
        self,
        level: str,
        lang: str,
        *,
        step_text: str,
        question: str,
    ) -> str:
        """Ответ на вопрос пользователя посреди урока."""
        return await self._request_text(
            task="lesson_question",
            level=level,
            lang=lang,
            prompt=tasks.lesson_question_prompt(step_text, wrap_user_text(question)),
            with_user_text=True,
            extra=tasks.LESSON_QUESTION_RULES,
        )

    # --- транспорт -----------------------------------------------------

    def _payload(
        self,
        *,
        level: str,
        lang: str,
        prompt: str,
        with_user_text: bool,
        json_mode: bool,
        extra: str = "",
        history: Sequence[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        """Тело запроса в формате OpenAI: модель, системный промпт, история, вопрос.

        JSON-режим `response_format` не используется: часть провайдеров отвечает
        на него ошибкой 502, а промпт «только JSON» и парсер с повторами надёжнее.
        """
        system_prompt = build_system_prompt(
            level,
            lang,
            extra=extra,
            with_user_text=with_user_text,
            json_mode=json_mode,
        )
        messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
        if history:
            messages.extend({"role": item["role"], "content": item["content"]} for item in history)
        messages.append({"role": "user", "content": prompt})
        return {"model": self.model, "messages": messages}

    async def _send(self, payload: dict[str, Any], task: str, prompt: str) -> str:
        """Один запрос к ИИ: логирование времени и токенов, разбор конверта."""
        headers = {"Content-Type": "application/json", BOT_TITLE_HEADER: "LinguaFlame"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        url = f"{self.base_url}{CHAT_COMPLETIONS_PATH}"

        started = time.perf_counter()
        try:
            response = await self._client.post(url, json=payload, headers=headers)
        except httpx.TimeoutException as exc:
            raise AITimeoutError(f"Таймаут {self.timeout}с при обращении к ИИ") from exc
        except httpx.TransportError as exc:
            raise AIRequestError(f"ИИ-сервер недоступен: {exc}") from exc
        elapsed_ms = int((time.perf_counter() - started) * 1000)

        if response.status_code >= 500 or response.status_code == RATE_LIMIT_STATUS:
            raise AIRequestError(f"ИИ-сервер вернул {response.status_code}: {response.text[:200]}")
        if response.status_code >= 400:
            raise AIRequestRejected(
                f"ИИ-сервер отклонил запрос: {response.status_code} {response.text[:200]}"
            )

        data = self._decode(response)
        content = self._extract_content(data)
        self._log_usage(task, prompt, content, elapsed_ms, data.get("usage"))
        return content

    @staticmethod
    def _decode(response: httpx.Response) -> dict[str, Any]:
        """Разбирает конверт OpenAI; не-JSON тело — ошибка ответа."""
        try:
            data = response.json()
        except ValueError as exc:
            raise AIResponseError("ИИ вернул не JSON") from exc
        if not isinstance(data, dict):
            raise AIResponseError("ИИ вернул не объект")
        return data

    @staticmethod
    def _extract_content(data: dict[str, Any]) -> str:
        """Достаёт текст ответа из choices[0].message.content."""
        choices = data.get("choices") or []
        message = (choices[0].get("message") or {}) if choices else {}
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            reason = data.get("error") or data
            raise AIResponseError(
                f"В ответе ИИ нет текста: {json.dumps(reason, ensure_ascii=False)[:200]}"
            )
        return content

    def _log_usage(
        self,
        task: str,
        prompt: str,
        content: str,
        elapsed_ms: int,
        usage: Any,
    ) -> None:
        """Пишет в лог время ответа и расход токенов (точные или оценку)."""
        if isinstance(usage, dict) and {"prompt_tokens", "completion_tokens"} <= set(usage):
            logger.info(
                "ИИ %s: %d мс, токены промпт=%d ответ=%d",
                task,
                elapsed_ms,
                int(usage["prompt_tokens"]),
                int(usage["completion_tokens"]),
            )
            return
        logger.info(
            "ИИ %s: %d мс, оценка токенов промпт≈%d ответ≈%d (символы %d/%d)",
            task,
            elapsed_ms,
            len(prompt) // CHARS_PER_TOKEN,
            len(content) // CHARS_PER_TOKEN,
            len(prompt),
            len(content),
        )

    async def _before_retry(self, retry_number: int, task: str, error: Exception) -> None:
        """Экспоненциальная пауза перед повтором: base, base*2, base*4."""
        delay = self.retry_delay * 2 ** (retry_number - 1)
        logger.warning(
            "ИИ %s: %s. Повтор %d из %d через %.1f с",
            task,
            error,
            retry_number,
            self.max_retries,
            delay,
        )
        await self._sleep(delay)

    async def _request_json(
        self,
        schema: type[SchemaT],
        *,
        task: str,
        level: str,
        lang: str,
        prompt: str,
        with_user_text: bool = False,
        extra: str = "",
        history: Sequence[dict[str, str]] | None = None,
    ) -> SchemaT:
        """Ответ как JSON нужной схемы; битый ответ — до 2 повторов."""
        payload = self._payload(
            level=level,
            lang=lang,
            prompt=prompt,
            with_user_text=with_user_text,
            json_mode=True,
            extra=extra,
            history=history,
        )

        last_error: AIError | None = None
        for attempt in range(self.max_retries + 1):
            if attempt:
                await self._before_retry(attempt, task, last_error or AIError("?"))
            try:
                text = await self._send(payload, task, prompt)
            except AITimeoutError:
                raise  # повтор после таймаута только удвоит ожидание
            except (AIRequestError, AIResponseError) as exc:
                last_error = exc
                continue
            try:
                return schema.model_validate(parse_json_payload(text))
            except (json.JSONDecodeError, ValidationError) as exc:
                last_error = AIResponseError(
                    f"Ответ ИИ не подходит под схему {schema.__name__}: {exc}"
                )
                logger.warning("Ответ ИИ невалиден (%s): %s", schema.__name__, exc)
        raise last_error or AIError("ИИ не ответил")

    async def _request_text(
        self,
        *,
        task: str,
        level: str,
        lang: str,
        prompt: str,
        with_user_text: bool = False,
        extra: str = "",
        history: Sequence[dict[str, str]] | None = None,
    ) -> str:
        """Ответ как обычный текст (свободный чат, вопрос внутри урока)."""
        payload = self._payload(
            level=level,
            lang=lang,
            prompt=prompt,
            with_user_text=with_user_text,
            json_mode=False,
            extra=extra,
            history=history,
        )

        last_error: AIError | None = None
        for attempt in range(self.max_retries + 1):
            if attempt:
                await self._before_retry(attempt, task, last_error or AIError("?"))
            try:
                text = await self._send(payload, task, prompt)
            except AITimeoutError:
                raise  # повтор после таймаута только удвоит ожидание
            except (AIRequestError, AIResponseError) as exc:
                last_error = exc
                continue
            cleaned = strip_markdown_fences(text)
            if cleaned:
                return cleaned
            last_error = AIResponseError("ИИ вернул пустой ответ")
        raise last_error or AIError("ИИ не ответил")


@lru_cache
def get_ai_client() -> AIClient:
    """Клиент из настроек: адрес, ключ и модель только из конфига."""
    settings = get_settings()
    return AIClient(
        base_url=settings.ai_server_url,
        api_key=settings.ai_api_key,
        model=settings.ai_model,
        timeout=settings.ai_timeout,
    )
