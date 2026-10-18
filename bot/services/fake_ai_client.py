"""Заглушка AI-клиента для тестов.

Методы повторяют сигнатуры `AIClient`, поэтому в тестах подставляется
вместо него: сетевых запросов нет, а вызовы записываются в `calls`.
"""

from collections.abc import Iterable, Sequence
from typing import Any

from bot.prompts import tasks
from bot.services.ai_schemas import (
    EssayCheck,
    LessonPlan,
    QuizQuestion,
    VocabularyResponse,
    Word,
)

DEFAULT_QUIZ_QUESTION = QuizQuestion(
    question="I ___ a student.",
    options={"A": "am", "B": "is", "C": "are"},
    correct="A",
    explanation="С местоимением I используется am.",
)

# 20 слов, чтобы набор проходил проверку «ровно 20 слов».
DEFAULT_WORDS = (
    "apple",
    "book",
    "city",
    "day",
    "evening",
    "family",
    "garden",
    "home",
    "idea",
    "journey",
    "kitchen",
    "letter",
    "morning",
    "night",
    "orange",
    "people",
    "question",
    "river",
    "school",
    "window",
)

DEFAULT_VOCABULARY = VocabularyResponse(
    words=[
        Word(word=word, transcription=f"/{word}/", translation=f"перевод: {word}")
        for word in DEFAULT_WORDS
    ]
)

DEFAULT_LESSON_PLAN = LessonPlan(
    topic="Present Simple",
    steps=[
        {"type": "explanation", "text": "Present Simple описывает регулярные действия."},
        {"type": "example", "text": "I read a book every day."},
        {"type": "exercise", "question": "He ___ to work by bus.", "answer": "goes"},
    ],
    final_test=[
        {
            "question": "She ___ coffee.",
            "options": {"A": "like", "B": "likes", "C": "liking"},
            "correct": "B",
        },
        {
            "question": "They ___ football every Sunday.",
            "options": {"A": "play", "B": "plays", "C": "playing"},
            "correct": "A",
        },
        {
            "question": "I ___ tea in the morning.",
            "options": {"A": "drinks", "B": "drink", "C": "drinking"},
            "correct": "B",
        },
        {
            "question": "We ___ not watch TV.",
            "options": {"A": "do", "B": "does", "C": "doing"},
            "correct": "A",
        },
        {
            "question": "___ he like apples?",
            "options": {"A": "Do", "B": "Does", "C": "Is"},
            "correct": "B",
        },
    ],
)

DEFAULT_ESSAY_CHECK = EssayCheck(
    overall_band=6.5,
    criteria={
        "task_response": 6.0,
        "coherence": 7.0,
        "lexical_resource": 6.5,
        "grammar": 6.5,
    },
    weak_spots=[{"quote": "people is happy", "problem": "согласование", "fix": "people are happy"}],
    summary="Хорошая структура, расширить аргументацию.",
)

DEFAULT_CHAT_ANSWER = "Nice to meet you! How are you today?"
DEFAULT_LESSON_ANSWER = "We use 'am' with I. Продолжим урок."


class FakeAIClient:
    """Отдаёт заранее заданные ответы и запоминает запросы."""

    def __init__(
        self,
        *,
        quiz: QuizQuestion | None = None,
        vocabulary: VocabularyResponse | None = None,
        lesson_plan: LessonPlan | None = None,
        essay: EssayCheck | None = None,
        chat: str | None = None,
        lesson_answer: str | None = None,
        error: Exception | None = None,
    ) -> None:
        self.quiz = quiz or DEFAULT_QUIZ_QUESTION
        self.vocabulary = vocabulary or DEFAULT_VOCABULARY
        self.lesson_plan = lesson_plan or DEFAULT_LESSON_PLAN
        self.essay = essay or DEFAULT_ESSAY_CHECK
        self.chat = chat or DEFAULT_CHAT_ANSWER
        self.lesson_answer = lesson_answer or DEFAULT_LESSON_ANSWER
        self.error = error
        self.calls: list[dict[str, Any]] = []

    async def close(self) -> None:
        """Совместимость с AIClient."""

    async def generate_quiz(self, level: str, lang: str) -> QuizQuestion:
        self._record("quiz", level=level, lang=lang)
        return self._result(self.quiz)

    async def generate_vocabulary(
        self,
        level: str,
        lang: str,
        *,
        count: int = tasks.WORDS_PER_DAY,
        exclude_words: Iterable[str] = (),
    ) -> VocabularyResponse:
        self._record(
            "vocabulary", level=level, lang=lang, count=count, exclude_words=list(exclude_words)
        )
        return self._result(self.vocabulary)

    async def generate_lesson_plan(
        self,
        level: str,
        lang: str,
        *,
        topic: str | None = None,
    ) -> LessonPlan:
        self._record("lesson_plan", level=level, lang=lang, topic=topic)
        return self._result(self.lesson_plan)

    async def check_essay(self, level: str, lang: str, text: str) -> EssayCheck:
        self._record("essay_check", level=level, lang=lang, text=text)
        return self._result(self.essay)

    async def free_chat(
        self,
        level: str,
        lang: str,
        *,
        history: Sequence[dict[str, str]] = (),
        text: str,
    ) -> str:
        self._record("free_chat", level=level, lang=lang, text=text, history=list(history))
        return self._result(self.chat)

    async def ask_in_lesson(
        self,
        level: str,
        lang: str,
        *,
        step_text: str,
        question: str,
    ) -> str:
        self._record(
            "lesson_question", level=level, lang=lang, step_text=step_text, question=question
        )
        return self._result(self.lesson_answer)

    def _record(self, task: str, **kwargs: Any) -> None:
        self.calls.append({"task": task, **kwargs})

    def _result(self, value: Any) -> Any:
        if self.error is not None:
            raise self.error
        return value

    def calls_of(self, task: str) -> list[dict[str, Any]]:
        """Все вызовы одной задачи — удобно проверять в тестах."""
        return [call for call in self.calls if call["task"] == task]
