"""Тесты дневного лимита запросов к ИИ."""

from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.middlewares.ai import AIClientMiddleware
from bot.repositories import AIUsageRepo, UserRepo
from bot.services.ai_errors import AIQuotaExceeded
from bot.services.ai_quota import QuotaAIClient
from bot.services.fake_ai_client import FakeAIClient

USER_ID = 4001
OTHER_USER = 4002
MOMENT = datetime(2026, 10, 18, 12, 0, tzinfo=UTC)


async def _user(
    session: AsyncSession,
    user_id: int = USER_ID,
    timezone_name: str = "Asia/Samarkand",
):
    repo = UserRepo(session)
    return await repo.create(user_id, native_language="ru", timezone=timezone_name)


async def test_quota_allows_requests_up_to_limit(session: AsyncSession) -> None:
    user = await _user(session)
    client = QuotaAIClient(FakeAIClient(), session, user, 2, now=MOMENT)

    await client.generate_quiz("B1", "ru")
    await client.generate_quiz("B1", "ru")

    usage = await AIUsageRepo(session).get(USER_ID, datetime(2026, 10, 18).date())
    assert usage is not None
    assert usage.requests == 2


async def test_quota_blocks_extra_request(session: AsyncSession) -> None:
    user = await _user(session)
    client = QuotaAIClient(FakeAIClient(), session, user, 1, now=MOMENT)

    await client.generate_quiz("B1", "ru")
    with pytest.raises(AIQuotaExceeded) as exc:
        await client.generate_quiz("B1", "ru")

    assert exc.value.user_message_key == "common.ai_limit"


async def test_quota_resets_next_local_day(session: AsyncSession) -> None:
    user = await _user(session)
    limit = 1
    first = QuotaAIClient(FakeAIClient(), session, user, limit, now=MOMENT)
    await first.generate_quiz("B1", "ru")

    next_day = QuotaAIClient(
        FakeAIClient(),
        session,
        user,
        limit,
        now=datetime(2026, 10, 19, 12, 0, tzinfo=UTC),
    )
    await next_day.generate_quiz("B1", "ru")

    assert (await AIUsageRepo(session).get(USER_ID, datetime(2026, 10, 18).date())).requests == 1
    assert (await AIUsageRepo(session).get(USER_ID, datetime(2026, 10, 19).date())).requests == 1


async def test_quota_counts_users_separately(session: AsyncSession) -> None:
    first = await _user(session, USER_ID)
    second = await _user(session, OTHER_USER)
    limit = 1

    await QuotaAIClient(FakeAIClient(), session, first, limit, now=MOMENT).generate_quiz("B1", "ru")
    await QuotaAIClient(FakeAIClient(), session, second, limit, now=MOMENT).generate_quiz(
        "B1", "ru"
    )

    assert (await AIUsageRepo(session).get(USER_ID, datetime(2026, 10, 18).date())).requests == 1
    assert (await AIUsageRepo(session).get(OTHER_USER, datetime(2026, 10, 18).date())).requests == 1


async def test_middleware_wraps_client_with_quota(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        async with session.begin():
            user = await _user(session)
            fake = FakeAIClient()
            middleware = AIClientMiddleware(client=fake, daily_limit=1)
            seen: dict[str, Any] = {}

            async def handler(event: Any, data: dict[str, Any]) -> None:
                seen["ai"] = data["ai"]
                await data["ai"].generate_quiz("B1", "ru")
                await data["ai"].generate_quiz("B1", "ru")

            with pytest.raises(AIQuotaExceeded):
                await middleware(handler, object(), {"session": session, "user": user})

    assert isinstance(seen["ai"], QuotaAIClient)
    assert len(fake.calls_of("quiz")) == 1


async def test_middleware_without_limit_uses_plain_client(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        async with session.begin():
            user = await _user(session)
            fake = FakeAIClient()
            middleware = AIClientMiddleware(client=fake, daily_limit=0)
            seen: dict[str, Any] = {}

            async def handler(event: Any, data: dict[str, Any]) -> None:
                seen["ai"] = data["ai"]

            await middleware(handler, object(), {"session": session, "user": user})

    assert seen["ai"] is fake


async def test_quota_client_forwards_all_task_methods(session: AsyncSession) -> None:
    user = await _user(session)
    fake = FakeAIClient()
    client = QuotaAIClient(fake, session, user, 10, now=MOMENT)

    await client.generate_vocabulary("A2", "ru", count=5)
    await client.generate_lesson_plan("A2", "ru", topic="Present Simple")
    await client.check_essay("B1", "ru", "text")
    await client.free_chat("B1", "ru", text="hi")
    await client.ask_in_lesson("B1", "ru", step_text="step", question="why?")

    assert [call["task"] for call in fake.calls] == [
        "vocabulary",
        "lesson_plan",
        "essay_check",
        "free_chat",
        "lesson_question",
    ]
    usage = await AIUsageRepo(session).get(USER_ID, datetime(2026, 10, 18).date())
    assert usage is not None
    assert usage.requests == 5
