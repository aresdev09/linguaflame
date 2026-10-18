"""Схемы ответов AI-сервера.

Форматы ответов без изменений: квиз-вопрос, список слов,
план урока и проверка эссе. Свободный чат — обычный текст, схемы не имеет.
"""

from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints, model_validator

# Обязательный непустой текст: пустые слова/переводы ломают карточку слова.
RequiredText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class QuizQuestion(BaseModel):
    """Один вопрос квиза с вариантами A, B, C."""

    question: str
    options: dict[str, str]
    correct: str
    explanation: str

    @model_validator(mode="after")
    def _check_options(self) -> "QuizQuestion":
        if not self.options:
            raise ValueError("options не может быть пустым")
        if self.correct not in self.options:
            raise ValueError(
                f"correct={self.correct!r} нет среди вариантов {sorted(self.options)}"
            )
        return self


class Word(BaseModel):
    """Слово с транскрипцией и переводом на родной язык пользователя."""

    word: RequiredText
    transcription: RequiredText
    translation: RequiredText


class VocabularyResponse(BaseModel):
    """Набор слов за день."""

    words: list[Word]


class LessonStep(BaseModel):
    """Шаг урока: объяснение, пример или упражнение."""

    type: Literal["explanation", "example", "exercise"]
    text: str | None = None
    question: str | None = None
    answer: str | None = None

    @model_validator(mode="after")
    def _check_step(self) -> "LessonStep":
        if self.type == "exercise":
            if not self.question:
                raise ValueError("у шага exercise должно быть поле question")
        elif not self.text:
            raise ValueError(f"у шага {self.type} должно быть поле text")
        return self


class LessonTestQuestion(BaseModel):
    """Вопрос мини-теста в конце урока."""

    question: str
    options: dict[str, str]
    correct: str

    @model_validator(mode="after")
    def _check_options(self) -> "LessonTestQuestion":
        if not self.options:
            raise ValueError("options не может быть пустым")
        if self.correct not in self.options:
            raise ValueError(
                f"correct={self.correct!r} нет среди вариантов {sorted(self.options)}"
            )
        return self


class LessonPlan(BaseModel):
    """План урока по грамматике: шаги плюс финальный мини-тест."""

    topic: str
    steps: list[LessonStep]
    final_test: list[LessonTestQuestion] = Field(default_factory=list)


class EssayCriteria(BaseModel):
    """Четыре критерия IELTS Writing Task 2, каждый от 0 до 9."""

    task_response: float = Field(ge=0, le=9)
    coherence: float = Field(ge=0, le=9)
    lexical_resource: float = Field(ge=0, le=9)
    grammar: float = Field(ge=0, le=9)


class EssayWeakSpot(BaseModel):
    """Слабое место: цитата из текста, суть проблемы и исправление."""

    quote: str
    problem: str
    fix: str


class EssayCheck(BaseModel):
    """Результат проверки эссе."""

    overall_band: float = Field(ge=0, le=9)
    criteria: EssayCriteria
    weak_spots: list[EssayWeakSpot]
    summary: str