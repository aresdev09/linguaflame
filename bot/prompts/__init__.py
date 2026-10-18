"""Шаблоны промптов AI-сервера."""

from bot.prompts.base import (
    BASE_SYSTEM_PROMPT,
    USER_TEXT_RULE,
    build_system_prompt,
    wrap_user_text,
)
from bot.prompts.tasks import (
    FREE_CHAT_RULES,
    LESSON_QUESTION_RULES,
    WORDS_PER_DAY,
    essay_prompt,
    lesson_plan_prompt,
    lesson_question_prompt,
    quiz_prompt,
    vocabulary_prompt,
)

__all__ = [
    "BASE_SYSTEM_PROMPT",
    "FREE_CHAT_RULES",
    "LESSON_QUESTION_RULES",
    "USER_TEXT_RULE",
    "WORDS_PER_DAY",
    "build_system_prompt",
    "essay_prompt",
    "lesson_plan_prompt",
    "lesson_question_prompt",
    "quiz_prompt",
    "vocabulary_prompt",
    "wrap_user_text",
]