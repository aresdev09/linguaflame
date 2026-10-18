"""Фоновые напоминания: APScheduler и почасовая рассылка.

Задача `check_streaks` запускается каждый час и сама выбирает пользователей,
у которых по их часовому поясу сейчас 09:00, 20:00 или 10:00. Решение,
тексты и обновление серии — в `bot.services.reminders`; здесь отправка,
пауза между сообщениями и обработка ошибок Telegram.

Задачи хранятся в Redis (`RedisJobStore`), чтобы переживать перезапуск бота.
Если Redis недоступен (локальная разработка), используется память процесса —
как и для FSM в `bot.main`.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib.parse import unquote, urlparse

import redis.asyncio as redis
from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
from apscheduler.jobstores.base import BaseJobStore
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.jobstores.redis import RedisJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.config import Settings, get_settings
from bot.database import get_session_factory
from bot.keyboards import reminder_quick_kb
from bot.models import User
from bot.repositories import UserRepo
from bot.services.reminders import (
    mark_reminder_sent,
    plan_reminder,
    reminder_allowed,
    reminder_text,
)
from bot.services.timezones import as_utc

logger = logging.getLogger(__name__)

CHECK_JOB_ID = "check_streaks"
CHECK_JOBSTORE = "default"

# Бот для задачи планировщика: объект Bot не сериализуется в RedisJobStore,
# поэтому задача хранится без аргументов и берёт бота отсюда.
_bot: Bot | None = None

# Не больше ~20 сообщений в секунду: пауза между отправками.
SEND_PAUSE = 0.05

# Задача раз в час; пропущенный запуск догоняем в пределах часа.
MISFIRE_GRACE_SEC = 3600


@dataclass(frozen=True)
class ReminderRun:
    """Итог одного прохода рассылки — удобно проверять в тестах и логах."""

    checked: int = 0
    sent: int = 0
    skipped: int = 0
    blocked: int = 0
    failed: int = 0


async def check_streaks(
    session_factory: async_sessionmaker[AsyncSession],
    bot: Bot,
    *,
    now: datetime | None = None,
    hour_offset: int = 0,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    pause: float = SEND_PAUSE,
) -> ReminderRun:
    """Один проход: кому и какое напоминание отправить.

    `now` и `hour_offset` нужны тестам и ручной проверке: сдвиг часов
    позволяет увидеть утреннее/вечернее сообщение, не дожидаясь нужного часа.
    """
    moment = as_utc(now) + timedelta(hours=hour_offset)
    checked = sent = skipped = blocked = failed = 0

    async with session_factory() as session:
        async with session.begin():
            users = await UserRepo(session).list_active_with_streaks()
            for user, streak in users:
                checked += 1
                reminder = plan_reminder(user, streak, moment)
                if reminder is None or not reminder_allowed(user, streak, moment):
                    skipped += 1
                    continue

                text = reminder_text(reminder, user, moment)
                try:
                    await _send(bot, user, text)
                except TelegramForbiddenError:
                    # Пользователь заблокировал бота: больше ему не пишем.
                    await UserRepo(session).deactivate(user.id)
                    blocked += 1
                    logger.info("Пользователь %s заблокировал бота", user.id)
                    continue
                except TelegramRetryAfter as exc:
                    await sleep(exc.retry_after)
                    try:
                        await _send(bot, user, text)
                    except TelegramForbiddenError:
                        await UserRepo(session).deactivate(user.id)
                        blocked += 1
                        continue
                    except Exception:
                        failed += 1
                        logger.exception(
                            "Повторная отправка напоминания %s не удалась", user.id
                        )
                        continue
                except Exception:
                    failed += 1
                    logger.exception(
                        "Не удалось отправить напоминание пользователю %s", user.id
                    )
                    continue

                await mark_reminder_sent(session, user, reminder, moment)
                sent += 1
                await sleep(pause)

    run = ReminderRun(
        checked=checked,
        sent=sent,
        skipped=skipped,
        blocked=blocked,
        failed=failed,
    )
    logger.info(
        "Напоминания: проверено %d, отправлено %d, пропущено %d, "
        "заблокировали %d, ошибок %d",
        run.checked,
        run.sent,
        run.skipped,
        run.blocked,
        run.failed,
    )
    return run


async def _send(bot: Bot, user: User, text: str) -> None:
    """Отправляет напоминание с кнопкой быстрого старта."""
    await bot.send_message(
        chat_id=user.id,
        text=text,
        reply_markup=reminder_quick_kb(user.native_language),
    )


async def run_hourly_check() -> ReminderRun:
    """Точка входа APScheduler: обычный час без сдвига."""
    if _bot is None:
        raise RuntimeError("Планировщик запущен без бота")
    settings = get_settings()
    return await check_streaks(
        get_session_factory(),
        _bot,
        hour_offset=settings.reminder_hour_offset,
    )


async def build_scheduler(bot: Bot, settings: Settings) -> AsyncIOScheduler:
    """Создаёт планировщик с задачей каждый час."""
    global _bot
    _bot = bot
    jobstore = await _pick_jobstore(settings.redis_url)
    scheduler = AsyncIOScheduler(
        jobstores={CHECK_JOBSTORE: jobstore},
        timezone=timezone.utc,
        job_defaults={"coalesce": True, "max_instances": 1},
    )
    scheduler.add_job(
        run_hourly_check,
        "cron",
        minute=0,
        id=CHECK_JOB_ID,
        replace_existing=True,
        misfire_grace_time=MISFIRE_GRACE_SEC,
    )
    return scheduler


async def _pick_jobstore(redis_url: str) -> BaseJobStore:
    """Redis для боевого режима, память — если Redis недоступен."""
    if await _redis_available(redis_url):
        return _redis_jobstore(redis_url)
    return MemoryJobStore()


def _redis_jobstore(redis_url: str) -> RedisJobStore:
    """RedisJobStore по URL: redis-py 5 не принимает `url` в Redis()."""
    parsed = urlparse(redis_url)
    db = (parsed.path or "/0").lstrip("/") or "0"
    options: dict[str, object] = {
        "host": parsed.hostname or "localhost",
        "port": parsed.port or 6379,
        "db": int(db),
    }
    if parsed.username:
        options["username"] = unquote(parsed.username)
    if parsed.password:
        options["password"] = unquote(parsed.password)
    if parsed.scheme == "rediss":
        options["ssl"] = True
    return RedisJobStore(**options)


async def _redis_available(redis_url: str) -> bool:
    """Проверяет Redis до старта планировщика, чтобы не падать на запуске."""
    client = redis.from_url(redis_url, socket_connect_timeout=1, socket_timeout=1)
    try:
        await client.ping()
        return True
    except Exception:
        logger.warning(
            "Redis недоступен (%s), задачи планировщика будут в памяти процесса",
            redis_url,
        )
        return False
    finally:
        await client.aclose()
