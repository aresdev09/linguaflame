"""Промпты под задачи: квиз, слова, урок, эссе, свободный чат.

Это тексты для модели, а не для пользователя, поэтому они на английском
и лежат здесь, а не в локализации. JSON-форматы ответов описаны ниже.
"""

from collections.abc import Iterable

WORDS_PER_DAY = 20

QUIZ_JSON_FORMAT = (
    '{"question": "...", "options": {"A": "...", "B": "...", "C": "..."}, '
    '"correct": "B", "explanation": "..."}'
)

VOCABULARY_JSON_FORMAT = (
    '{"words": [{"word": "...", "transcription": "/.../", "translation": "..."}]}'
)

LESSON_PLAN_JSON_FORMAT = (
    '{"topic": "Present Perfect", "steps": [{"type": "explanation", "text": "..."}, '
    '{"type": "example", "text": "..."}, {"type": "exercise", "question": "...", '
    '"answer": "..."}], "final_test": [{"question": "...", '
    '"options": {"A": "...", "B": "..."}, "correct": "A"}]}'
)

ESSAY_JSON_FORMAT = (
    '{"overall_band": 6.5, "criteria": {"task_response": 6.0, "coherence": 7.0, '
    '"lexical_resource": 6.5, "grammar": 6.5}, "weak_spots": [{"quote": "...", '
    '"problem": "...", "fix": "..."}], "summary": "..."}'
)

FREE_CHAT_RULES = (
    "Answer in the language the student writes in. "
    "If the student's English has mistakes, correct them gently. "
    "Keep the answer short."
)

LESSON_QUESTION_RULES = (
    "Answer the student's question about the current lesson step. "
    "Keep it short and finish with one line that returns to the lesson."
)


def quiz_prompt() -> str:
    """Задание на один вопрос квиза."""
    return (
        "Create one multiple-choice English question for the student.\n"
        "Use exactly three options A, B and C, and explain the correct answer "
        "in the student's native language.\n"
        f"Answer with JSON only, exactly this shape:\n{QUIZ_JSON_FORMAT}"
    )


def vocabulary_prompt(
    count: int = WORDS_PER_DAY,
    exclude_words: Iterable[str] = (),
) -> str:
    """Задание на набор слов с транскрипцией и переводом."""
    prompt = (
        f"Create exactly {count} useful English words for the student.\n"
        "Give an IPA transcription like /ˈwɜːd/ and a translation "
        "into the student's native language.\n"
        f"Answer with JSON only, exactly this shape:\n{VOCABULARY_JSON_FORMAT}"
    )
    excluded = sorted({word.strip() for word in exclude_words if word.strip()})
    if excluded:
        prompt += "\nDo not repeat these words: " + ", ".join(excluded)
    return prompt


def lesson_plan_prompt(topic: str | None = None) -> str:
    """Задание на план урока по грамматике."""
    topic_line = f'The topic is "{topic}".' if topic else "Choose one useful topic yourself."
    return (
        f"Create a grammar lesson plan for the student. {topic_line}\n"
        "Steps must follow one by one: explanation, example, exercise. "
        "Finish with 5 multiple-choice questions for the final test.\n"
        f"Answer with JSON only, exactly this shape:\n{LESSON_PLAN_JSON_FORMAT}"
    )


def essay_prompt(user_text: str) -> str:
    """Задание на проверку эссе по критериям IELTS."""
    return (
        "Check the essay below using the four IELTS Writing Task 2 criteria. "
        "Be conservative: list up to 7 weak spots with a quote, the problem "
        "and the correction. Write explanations in the student's native language.\n"
        f"Answer with JSON only, exactly this shape:\n{ESSAY_JSON_FORMAT}\n\n"
        f"Student essay:\n{user_text}"
    )


def lesson_question_prompt(step_text: str, question: str) -> str:
    """Задание на вопрос пользователя посреди урока."""
    return (
        "The student is in the middle of a lesson and asks a question.\n"
        f"Current step:\n{step_text}\n\n"
        f"Student question:\n{question}"
    )