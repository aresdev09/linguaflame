"""Сервисы бота: бизнес-логика без aiogram-импортов."""

from bot.services.ai_client import (
    AIClient,
    get_ai_client,
    parse_json_payload,
    strip_markdown_fences,
)
from bot.services.ai_errors import (
    AIError,
    AIRequestError,
    AIRequestRejected,
    AIResponseError,
)
from bot.services.ai_schemas import (
    EssayCheck,
    EssayCriteria,
    EssayWeakSpot,
    LessonPlan,
    LessonStep,
    LessonTestQuestion,
    QuizQuestion,
    VocabularyResponse,
    Word,
)
from bot.services.fake_ai_client import FakeAIClient

__all__ = [
    "AIClient",
    "AIError",
    "AIRequestError",
    "AIRequestRejected",
    "AIResponseError",
    "EssayCheck",
    "EssayCriteria",
    "EssayWeakSpot",
    "FakeAIClient",
    "LessonPlan",
    "LessonStep",
    "LessonTestQuestion",
    "QuizQuestion",
    "VocabularyResponse",
    "Word",
    "get_ai_client",
    "parse_json_payload",
    "strip_markdown_fences",
]