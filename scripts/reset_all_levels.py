"""Массовый сброс уровней после исправления теста (разовый скрипт поддержки).

Сбрасывает `users.level` у всех, у кого он выставлен, и пишет каждому
пользователю, что нужно пройти /level_detector заново. Обычно уровень меняет
только тест; скрипт нужен после исправления ошибки подсчёта.
Запуск из корня проекта:
    python -m scripts.reset_all_levels --dry-run
    python -m scripts.reset_all_levels
"""

import argparse
import asyncio
import logging
import sys
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bot.config import get_settings
from bot.database import get_session_factory, transaction_with_retry
from bot.locales import t
from bot.logging_setup import setup_logging
from bot.repositories import UserRepo

logger = logging.getLogger(__name__)

# Не больше ~20 сообщений в секунду: пауза между отправками.
SEND_PAUSE = 0.05


@dataclass(frozen=True)
class ResetRun:
    """Итог массового сброса — удобно проверять в тестах и логах."""

    total: int = 0
    reset: int = 0
    sent: int = 0
    blocked: int = 0
    failed: int = 0


async def reset_all_levels(
    session_factory: async_sessionmaker[AsyncSession],
    bot: Bot,
    *,
    dry_run: bool = False,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    pause: float = SEND_PAUSE,
) -> ResetRun:
    """Сбрасывает уровни всех пользователей и рассылает уведомление.

    Записи идут короткими транзакциями, как в планировщике: одна общая
    транзакция держала бы блокировку записи во время всех отправок.
    """
    async with session_factory() as session:
        users = await UserRepo(session).list_with_level()
    total = len(users)

    if dry_run:
        print(f"К сбросу: {total} пользователей")
        for user in users:
            name = f"@{user.username}" if user.username else "—"
            print(f"  {user.id} — уровень {user.level}, {name}")
        return ResetRun(total=total)

    reset = sent = blocked = failed = 0
    for user in users:
        # Сначала сбрасываем уровень — сообщение обещает именно это.
        await transaction_with_retry(
            session_factory,
            lambda session, uid=user.id: UserRepo(session).reset_level(uid),
        )
        reset += 1

        text = t("level.reset_notice", user.native_language)
        try:
            await bot.send_message(chat_id=user.id, text=text)
        except TelegramForbiddenError:
            # Пользователь заблокировал бота: больше ему не пишем.
            await _deactivate(session_factory, user.id)
            blocked += 1
            logger.info("Пользователь %s заблокировал бота", user.id)
            continue
        except TelegramRetryAfter as exc:
            await sleep(exc.retry_after)
            try:
                await bot.send_message(chat_id=user.id, text=text)
            except TelegramForbiddenError:
                await _deactivate(session_factory, user.id)
                blocked += 1
                continue
            except Exception:
                failed += 1
                logger.exception("Повторная отправка уведомления %s не удалась", user.id)
                continue
        except Exception:
            failed += 1
            logger.exception("Не удалось отправить уведомление пользователю %s", user.id)
            continue

        sent += 1
        await sleep(pause)

    run = ResetRun(total=total, reset=reset, sent=sent, blocked=blocked, failed=failed)
    logger.info(
        "Сброс уровней: всего %d, сброшено %d, уведомлений %d, заблокировали %d, ошибок %d",
        run.total,
        run.reset,
        run.sent,
        run.blocked,
        run.failed,
    )
    return run


async def _deactivate(
    session_factory: async_sessionmaker[AsyncSession],
    user_id: int,
) -> None:
    """Помечает пользователя неактивным своей короткой транзакцией."""
    await transaction_with_retry(
        session_factory,
        lambda session: UserRepo(session).deactivate(user_id),
    )


async def main(dry_run: bool) -> int:
    """Запускает сброс на боевой базе и печатает итог."""
    bot = Bot(token=get_settings().bot_token)
    try:
        run = await reset_all_levels(get_session_factory(), bot, dry_run=dry_run)
    finally:
        await bot.session.close()

    if not dry_run:
        print(
            f"Всего с уровнем: {run.total}, сброшено: {run.reset}, "
            f"уведомлений: {run.sent}, заблокировали: {run.blocked}, ошибок: {run.failed}"
        )
    return 1 if run.failed else 0


if __name__ == "__main__":
    setup_logging()
    parser = argparse.ArgumentParser(
        description="Сбросить уровни всех пользователей и уведомить их (для поддержки)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="показать, кого затронет, ничего не меняя",
    )
    arguments = parser.parse_args()
    raise SystemExit(asyncio.run(main(arguments.dry_run)))
