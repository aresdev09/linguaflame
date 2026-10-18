"""ORM-модели базы данных.

Схема базы данных.
Все даты и время хранятся в UTC (`timestamptz` в PostgreSQL).
"""

from datetime import UTC, date, datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    true,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    """Текущее время в UTC."""
    return datetime.now(UTC)


# BIGINT в PostgreSQL, INTEGER в SQLite (нужен для автоинкремента primary key)
BigIntType = BigInteger().with_variant(Integer, "sqlite")


class Base(DeclarativeBase):
    """Базовый класс для всех моделей."""


class User(Base):
    """Пользователь бота, id — это Telegram user id."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigIntType, primary_key=True, autoincrement=False)
    username: Mapped[str | None] = mapped_column(Text)
    native_language: Mapped[str] = mapped_column(String(8))
    level: Mapped[str | None] = mapped_column(String(2))
    level_tested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    timezone: Mapped[str] = mapped_column(String(64), default="UTC", server_default="UTC")
    # Заблокировавшие бота пользователи: напоминания им больше не шлём.
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Streak(Base):
    """Серия дней пользователя («огонёк»)."""

    __tablename__ = "streaks"

    user_id: Mapped[int] = mapped_column(BigIntType, ForeignKey("users.id"), primary_key=True)
    current_streak: Mapped[int] = mapped_column(Integer, default=0)
    best_streak: Mapped[int] = mapped_column(Integer, default=0)
    last_activity_date: Mapped[date | None] = mapped_column(Date)
    last_reminder_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Счётчик напоминаний за локальный день: не больше 2 в сутки.
    reminders_date: Mapped[date | None] = mapped_column(Date)
    reminders_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")


class LevelTest(Base):
    """Прохождение теста уровня."""

    __tablename__ = "level_tests"

    id: Mapped[int] = mapped_column(BigIntType, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigIntType, ForeignKey("users.id"))
    # Порядок из 50 вопросов теста: нужен, чтобы продолжить незавершённый тест.
    question_ids: Mapped[list] = mapped_column(JSON, default=list)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    score: Mapped[float | None] = mapped_column(Float)
    total_time_sec: Mapped[int | None] = mapped_column(Integer)
    result_level: Mapped[str | None] = mapped_column(String(2))


class LevelTestAnswer(Base):
    """Ответ пользователя на вопрос теста уровня."""

    __tablename__ = "level_test_answers"

    id: Mapped[int] = mapped_column(BigIntType, primary_key=True)
    test_id: Mapped[int] = mapped_column(BigIntType, ForeignKey("level_tests.id"))
    question_id: Mapped[int] = mapped_column(BigIntType, ForeignKey("questions.id"))
    is_correct: Mapped[bool] = mapped_column(Boolean)
    answer_time_sec: Mapped[int] = mapped_column(Integer)


class Question(Base):
    """Банк вопросов для квиза и теста уровня."""

    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(BigIntType, primary_key=True)
    kind: Mapped[str] = mapped_column(
        Enum("grammar", "vocabulary", name="question_kind", native_enum=False)
    )
    level: Mapped[str] = mapped_column(String(2))
    text: Mapped[str] = mapped_column(Text)
    options: Mapped[dict] = mapped_column(JSON)
    correct_option: Mapped[str] = mapped_column(String(1))
    explanation: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (Index("ix_questions_kind_level", "kind", "level"),)


class VocabularySet(Base):
    """Набор слов, выданный пользователю за день."""

    __tablename__ = "vocabulary_sets"

    id: Mapped[int] = mapped_column(BigIntType, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigIntType, ForeignKey("users.id"))
    date: Mapped[date] = mapped_column(Date)
    words: Mapped[list] = mapped_column(JSON)


class Lesson(Base):
    """Урок по грамматике и его текущий прогресс."""

    __tablename__ = "lessons"

    id: Mapped[int] = mapped_column(BigIntType, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigIntType, ForeignKey("users.id"))
    topic: Mapped[str] = mapped_column(Text)
    level: Mapped[str] = mapped_column(String(2))
    plan: Mapped[dict] = mapped_column(JSON)
    current_step: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(
        Enum("active", "done", name="lesson_status", native_enum=False),
        default="active",
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (Index("ix_lessons_user_id_status", "user_id", "status"),)


class Essay(Base):
    """Проверенное эссе пользователя."""

    __tablename__ = "essays"

    id: Mapped[int] = mapped_column(BigIntType, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigIntType, ForeignKey("users.id"))
    text: Mapped[str] = mapped_column(Text)
    score_overall: Mapped[float] = mapped_column(Float)
    score_json: Mapped[dict] = mapped_column(JSON)
    feedback: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AIUsage(Base):
    """Дневной счётчик запросов к ИИ: ограничение расходов на пользователя."""

    __tablename__ = "ai_usage"

    user_id: Mapped[int] = mapped_column(BigIntType, ForeignKey("users.id"), primary_key=True)
    # Локальная дата пользователя: лимит сбрасывается в его полночь.
    day: Mapped[date] = mapped_column(Date, primary_key=True)
    requests: Mapped[int] = mapped_column(Integer, default=0, server_default="0")


class ActivityLog(Base):
    """Лог учебной активности пользователя (для серии дней и статистики)."""

    __tablename__ = "activity_log"

    id: Mapped[int] = mapped_column(BigIntType, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigIntType, ForeignKey("users.id"))
    kind: Mapped[str] = mapped_column(
        Enum(
            "quiz",
            "grammar",
            "vocabulary",
            "essay",
            "chat",
            "level_test",
            name="activity_kind",
            native_enum=False,
        )
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (Index("ix_activity_log_user_id_created_at", "user_id", "created_at"),)
