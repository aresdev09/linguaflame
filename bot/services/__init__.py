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
    AITimeoutError,
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
from bot.services.quiz import (
    QuizScore,
    format_quiz_feedback,
    format_quiz_question,
    format_quiz_result,
    next_quiz_question,
    score_quiz_answer,
)
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
    "AITimeoutError",
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
    "QuizScore",
    "UserStats",
    "VocabularyResponse",
    "Word",
    "as_utc",
    "format_daily_vocabulary",
    "format_quiz_feedback",
    "format_quiz_question",
    "format_quiz_result",
    "get_ai_client",
    "get_daily_vocabulary",
    "get_user_stats",
    "next_quiz_question",
    "parse_json_payload",
    "register_activity",
    "resolve_timezone",
    "score_quiz_answer",
    "strip_markdown_fences",
]
