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
from bot.services.streak import (
    ACTIVITY_KINDS,
    ActivityKind,
    ActivityResult,
    UserStats,
    get_user_stats,
    register_activity,
)
from bot.services.timezones import DEFAULT_TIMEZONE, as_utc, resolve_timezone
from bot.services.vocabulary import (
    DailyVocabulary,
    format_daily_vocabulary,
    get_daily_vocabulary,
)

__all__ = [
    "ACTIVITY_KINDS",
    "AIClient",
    "AIError",
    "AIRequestError",
    "AIRequestRejected",
    "AIResponseError",
    "ActivityKind",
    "ActivityResult",
    "DailyVocabulary",
    "DEFAULT_TIMEZONE",
    "EssayCheck",
    "EssayCriteria",
    "EssayWeakSpot",
    "FakeAIClient",
    "LessonPlan",
    "LessonStep",
    "LessonTestQuestion",
    "QuizQuestion",
    "UserStats",
    "VocabularyResponse",
    "Word",
    "as_utc",
    "format_daily_vocabulary",
    "get_ai_client",
    "get_daily_vocabulary",
    "get_user_stats",
    "parse_json_payload",
    "register_activity",
    "resolve_timezone",
    "strip_markdown_fences",
]