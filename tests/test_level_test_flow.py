"""Сценарии теста уровня: подтверждение, старт, ответы, продолжение, финал."""

from datetime import datetime, timedelta, timezone

from aiogram.fsm.context import FSMContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.config import LEVELS
from bot.keyboards import LEVEL_CANCEL_CALLBACK, LEVEL_START_CALLBACK
from bot.locales import t
from bot.models import ActivityLog, LevelTest, LevelTestAnswer, User
from bot.repositories import (
    LevelTestAnswerRepo,
    LevelTestRepo,
    QuestionRepo,
    UserRepo,
)
from bot.routers.level_detector import (
    _complete_test,
    level_callback,
    level_detector_command,
)
from bot.states import LevelTestStates
from tests.fakes import (
    FakeChat,
    FakeCallbackQuery,
    FakeMessage,
    callbacks,
    dispatch,
    make_state,
)

USER_ID = 803


async def _create_user(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    level: str | None = None,
    tested_at: datetime | None = None,
    timezone_name: str = "UTC",
) -> None:
    async with session_factory() as session:
        async with session.begin():
            repo = UserRepo(session)
            user = await repo.create(
                USER_ID, native_language="ru", timezone=timezone_name
            )
            if level is not None:
                await repo.set_level(USER_ID, level, tested_at or datetime.now(timezone.utc))
            await session.flush()
            assert user is not None


async def _seed_bank(session_factory: async_sessionmaker[AsyncSession]) -> None:
    """По 5 вопросов каждого вида на уровень — хватает на тест из 50."""
    async with session_factory() as session:
        async with session.begin():
            repo = QuestionRepo(session)
            for level in LEVELS:
                for kind in ("grammar", "vocabulary"):
                    for index in range(5):
                        await repo.create(
                            kind=kind,
                            level=level,
                            text=f"{level} {kind} question {index}",
                            options={"A": "one", "B": "two", "C": "three"},
                            correct_option="A",
                            explanation="Пояснение",
                        )


async def _start_test(
    session_factory: async_sessionmaker[AsyncSession],
    chat: FakeChat,
    state: FSMContext,
) -> None:
    await dispatch(
        session_factory,
        level_detector_command,
        FakeMessage(chat),
        state,
    )


def _question_id(markup: object) -> int:
    data = callbacks(markup)[0]
    _, raw_id, _ = data.split(":")
    return int(raw_id)


def _age_sent_at(seconds: int) -> str:
    moment = datetime.now(timezone.utc) - timedelta(seconds=seconds)
    return moment.isoformat()


async def test_retake_prompt_shows_current_level_and_date(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _create_user(
        session_factory,
        level="B1",
        tested_at=datetime(2026, 10, 12, 10, 0, tzinfo=timezone.utc),
    )
    await _seed_bank(session_factory)
    chat = FakeChat(USER_ID)
    state = make_state(USER_ID)

    await _start_test(session_factory, chat, state)

    assert chat.messages[-1] == t(
        "level.retake", "ru", level="B1", date="12.10.2026"
    )
    assert set(callbacks(chat.markups[-1])) == {
        LEVEL_START_CALLBACK,
        LEVEL_CANCEL_CALLBACK,
    }
    assert await state.get_state() is None


async def test_start_creates_test_and_keeps_level_until_finish(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _create_user(session_factory, level="B1")
    await _seed_bank(session_factory)
    chat = FakeChat(USER_ID)
    state = make_state(USER_ID)

    await _start_test(session_factory, chat, state)
    prompt_message = FakeMessage(chat, len(chat.messages) - 1)
    callback = FakeCallbackQuery(LEVEL_START_CALLBACK, prompt_message)
    await dispatch(session_factory, level_callback, callback, state)

    assert callback.answers == [""]
    assert chat.messages[prompt_message.index] == t("level.intro", "ru")
    question_message = chat.messages[-1]
    assert question_message.startswith("Вопрос 1 из 50")
    assert await state.get_state() == LevelTestStates.answering.state

    async with session_factory() as session:
        tests = list(await session.scalars(select(LevelTest)))
        assert len(tests) == 1
        assert len(tests[0].question_ids) == 50
        assert tests[0].finished_at is None
        user = await UserRepo(session).get(USER_ID)
        assert user is not None
        assert user.level == "B1"  # уровень меняется только после финала


async def test_answer_records_time_and_is_correct(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _create_user(session_factory)
    await _seed_bank(session_factory)
    chat = FakeChat(USER_ID)
    state = make_state(USER_ID)

    await _start_test(session_factory, chat, state)
    question_message = FakeMessage(chat, len(chat.messages) - 1)
    question_id = _question_id(chat.markups[-1])
    await state.update_data(sent_at=_age_sent_at(7))

    callback = FakeCallbackQuery(f"level:{question_id}:A", question_message)
    await dispatch(session_factory, level_callback, callback, state)

    assert callback.answers == [""]
    async with session_factory() as session:
        answers = list(await session.scalars(select(LevelTestAnswer)))
        assert len(answers) == 1
        assert answers[0].question_id == question_id
        assert answers[0].is_correct is True
        assert answers[0].answer_time_sec >= 7
        user = await UserRepo(session).get(USER_ID)
        assert user is not None
        assert user.level is None
        assert user.level_tested_at is None
        test = (await session.scalars(select(LevelTest))).one()
        assert test.finished_at is None

    data = await state.get_data()
    assert data["answered_count"] == 1
    assert data["answered"] is False  # уже задан следующий вопрос


async def test_interrupted_test_does_not_touch_level(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    tested_at = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)
    await _create_user(session_factory, level="A2", tested_at=tested_at)
    await _seed_bank(session_factory)
    chat = FakeChat(USER_ID)
    state = make_state(USER_ID)

    # Уровень есть — сначала подтверждение повторной сдачи.
    await _start_test(session_factory, chat, state)
    prompt = FakeMessage(chat, len(chat.messages) - 1)
    await dispatch(
        session_factory,
        level_callback,
        FakeCallbackQuery(LEVEL_START_CALLBACK, prompt),
        state,
    )
    question_message = FakeMessage(chat, len(chat.messages) - 1)
    question_id = _question_id(chat.markups[-1])
    await state.update_data(sent_at=_age_sent_at(5))
    await dispatch(
        session_factory,
        level_callback,
        FakeCallbackQuery(f"level:{question_id}:A", question_message),
        state,
    )

    async with session_factory() as session:
        user = await UserRepo(session).get(USER_ID)
        assert user is not None
        assert user.level == "A2"
        assert user.level_tested_at is not None
        assert user.level_tested_at.date() == tested_at.date()
        test = (await session.scalars(select(LevelTest))).one()
        assert test.finished_at is None


async def test_unfinished_test_is_resumed_without_new_test(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _create_user(session_factory)
    await _seed_bank(session_factory)
    chat = FakeChat(USER_ID)
    state = make_state(USER_ID)

    await _start_test(session_factory, chat, state)
    question_message = FakeMessage(chat, len(chat.messages) - 1)
    question_id = _question_id(chat.markups[-1])
    await state.update_data(sent_at=_age_sent_at(4))
    await dispatch(
        session_factory,
        level_callback,
        FakeCallbackQuery(f"level:{question_id}:A", question_message),
        state,
    )

    # Потеряли FSM (перезапуск): команда должна продолжить с вопроса 2.
    fresh_state = make_state(USER_ID)
    await _start_test(session_factory, chat, fresh_state)

    assert chat.messages[-2] == t("level.resume", "ru", number=2, total=50)
    assert chat.messages[-1].startswith("Вопрос 2 из 50")
    assert await fresh_state.get_state() == LevelTestStates.answering.state

    async with session_factory() as session:
        tests = list(await session.scalars(select(LevelTest)))
        assert len(tests) == 1
        assert tests[0].finished_at is None


async def test_double_click_does_not_add_answer(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _create_user(session_factory)
    await _seed_bank(session_factory)
    chat = FakeChat(USER_ID)
    state = make_state(USER_ID)

    await _start_test(session_factory, chat, state)
    question_message = FakeMessage(chat, len(chat.messages) - 1)
    question_id = _question_id(chat.markups[-1])
    await state.update_data(sent_at=_age_sent_at(3))
    await dispatch(
        session_factory,
        level_callback,
        FakeCallbackQuery(f"level:{question_id}:A", question_message),
        state,
    )

    repeated = FakeCallbackQuery(f"level:{question_id}:A", question_message)
    await dispatch(session_factory, level_callback, repeated, state)

    assert repeated.answers == [t("level.already_answered", "ru")]
    async with session_factory() as session:
        answers = list(await session.scalars(select(LevelTestAnswer)))
        assert len(answers) == 1
    data = await state.get_data()
    assert data["answered_count"] == 1


async def test_complete_test_writes_level_and_activity_once(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _create_user(session_factory)

    async with session_factory() as session:
        async with session.begin():
            repo = QuestionRepo(session)
            first = await repo.create(
                kind="grammar",
                level="A1",
                text="Первый",
                options={"A": "one", "B": "two", "C": "three"},
                correct_option="A",
            )
            second = await repo.create(
                kind="vocabulary",
                level="A1",
                text="Второй",
                options={"A": "one", "B": "two", "C": "three"},
                correct_option="A",
            )
            user = await session.get(User, USER_ID)
            assert user is not None
            test = await LevelTestRepo(session).create(
                USER_ID, [first.id, second.id]
            )
            answers = LevelTestAnswerRepo(session)
            await answers.add(
                test.id, first.id, is_correct=False, answer_time_sec=5
            )
            await answers.add(
                test.id, second.id, is_correct=False, answer_time_sec=5
            )
            result = await _complete_test(session, test, user)

    assert result is not None
    assert result.level == "A1"

    async with session_factory() as session:
        user = await UserRepo(session).get(USER_ID)
        assert user is not None
        assert user.level == "A1"
        assert user.level_tested_at is not None
        test = (await session.scalars(select(LevelTest))).one()
        assert test.finished_at is not None
        assert test.result_level == "A1"
        assert test.score == result.percent
        kinds = list(await session.scalars(select(ActivityLog.kind)))
        assert kinds == ["level_test"]


async def test_incomplete_answers_do_not_write_level(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _create_user(session_factory)

    async with session_factory() as session:
        async with session.begin():
            repo = QuestionRepo(session)
            first = await repo.create(
                kind="grammar",
                level="A1",
                text="Первый",
                options={"A": "one", "B": "two", "C": "three"},
                correct_option="A",
            )
            second = await repo.create(
                kind="vocabulary",
                level="A1",
                text="Второй",
                options={"A": "one", "B": "two", "C": "three"},
                correct_option="A",
            )
            user = await session.get(User, USER_ID)
            assert user is not None
            test = await LevelTestRepo(session).create(
                USER_ID, [first.id, second.id]
            )
            await LevelTestAnswerRepo(session).add(
                test.id, first.id, is_correct=True, answer_time_sec=5
            )
            result = await _complete_test(session, test, user)

    assert result is None

    async with session_factory() as session:
        user = await UserRepo(session).get(USER_ID)
        assert user is not None
        assert user.level is None
        assert user.level_tested_at is None
