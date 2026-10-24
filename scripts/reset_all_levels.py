"""Массовый сброс уровней после исправления теста (разовый скрипт поддержки).

По умолчанию сбрасывает только завышенные уровни: последний завершённый тест
каждого пользователя пересчитывается по текущим правилам, и если записанный
уровень выше пересчитанного — уровень сбрасывается и уходит уведомление,
остальных не трогаем.

С `--all` сбрасывает уровни у всех, у кого они выставлены.
Запуск из корня проекта:
    python -m scripts.reset_all_levels --dry-run
    python -m scripts.reset_all_levels
    python -m scripts.reset_all_levels --all
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

from bot.config import LEVELS, get_settings
from bot.database import get_session_factory, transaction_with_retry
from bot.locales import t
from bot.logging_setup import setup_logging
from bot.models import User
from bot.repositories import LevelTestRepo, UserRepo
from bot.services.level_test import recalculate_test_result

logger = logging.getLogger(__name__)

# Не больше ~20 сообщений в секунду: пауза между отправками.
SEND_PAUSE = 0.05


@dataclass(frozen=True)
class ResetRun:
    """Итог массового сброса — удобно проверять в тестах и логах."""

    total: int = 0  # пользователей с выставленным уровнем
    wrong: int = 0  # из них с завышенным уровнем
    unverified: int = 0  # уровень есть, а завершённого теста нет
    reset: int = 0
    sent: int = 0
    blocked: int = 0
    failed: int = 0


@dataclass(frozen=True)
class ResetTarget:
    """Кого сбросить и что показывает исправленный расчёт."""

    user: User
    fixed_level: str | None  # None: режим --all, уровень просто очищается


async def _find_targets(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    only_wrong: bool,
) -> tuple[list[ResetTarget], ResetRun]:
    """Отбирает пользователей и считает статистику, ничего не меняя."""
    async with session_factory() as session:
        users = await UserRepo(session).list_with_level()
        targets: list[ResetTarget] = []
        wrong = unverified = 0

        if not only_wrong:
            targets = [ResetTarget(user=user, fixed_level=None) for user in users]
        else:
            tests = LevelTestRepo(session)
            for user in users:
                stored = user.level
                if stored is None:
                    continue
                test = await tests.get_latest_finished(user.id)
                computed = await recalculate_test_result(session, test) if test else None
                if computed is None:
                    unverified += 1
                    continue
                if LEVELS.index(stored) > LEVELS.index(computed.level):
                    wrong += 1
                    targets.append(ResetTarget(user=user, fixed_level=computed.level))

    stats = ResetRun(total=len(users), wrong=wrong, unverified=unverified)
    return targets, stats


def _dry_run_report(
    targets: list[ResetTarget],
    stats: ResetRun,
    *,
    only_wrong: bool,
) -> str:
    """Текст отчёта для `--dry-run`: кого затронет и что покажет пересчёт."""
    if only_wrong:
        lines = [
            f"С завышенным уровнем: {stats.wrong} из {stats.total} "
            f"(без завершённого теста: {stats.unverified})"
        ]
    else:
        lines = [f"К сбросу: {stats.total} пользователей"]

    for target in targets:
        user = target.user
        name = f"@{user.username}" if user.username else "—"
        level = f"{user.level} → {target.fixed_level}" if target.fixed_level else str(user.level)
        lines.append(f"  {user.id} — уровень {level}, {name}")
    return "\n".join(lines)


async def reset_all_levels(
    session_factory: async_sessionmaker[AsyncSession],
    bot: Bot,
    *,
    only_wrong: bool = True,
    dry_run: bool = False,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    pause: float = SEND_PAUSE,
) -> ResetRun:
    """Сбрасывает выбранные уровни и рассылает уведомление.

    only_wrong=True (по умолчанию) — только завышенные уровни.
    Записи идут короткими транзакциями, как в планировщике: одна общая
    транзакция держала бы блокировку записи во время всех отправок.
    """
    targets, stats = await _find_targets(session_factory, only_wrong=only_wrong)

    if dry_run:
        print(_dry_run_report(targets, stats, only_wrong=only_wrong))
        return stats

    reset = sent = blocked = failed = 0
    for target in targets:
        user = target.user
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

    run = ResetRun(
        total=stats.total,
        wrong=stats.wrong,
        unverified=stats.unverified,
        reset=reset,
        sent=sent,
        blocked=blocked,
        failed=failed,
    )
    logger.info(
        "Сброс уровней: всего %d, завышенных %d, без теста %d, сброшено %d, "
        "уведомлений %d, заблокировали %d, ошибок %d",
        run.total,
        run.wrong,
        run.unverified,
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


async def main(only_wrong: bool, dry_run: bool) -> int:
    """Запускает сброс на боевой базе и печатает итог."""
    bot = Bot(token=get_settings().bot_token)
    try:
        run = await reset_all_levels(
            get_session_factory(),
            bot,
            only_wrong=only_wrong,
            dry_run=dry_run,
        )
    finally:
        await bot.session.close()

    if not dry_run:
        print(
            f"Всего с уровнем: {run.total}, завышенных: {run.wrong}, "
            f"без завершённого теста: {run.unverified}, сброшено: {run.reset}, "
            f"уведомлений: {run.sent}, заблокировали: {run.blocked}, ошибок: {run.failed}"
        )
    return 1 if run.failed else 0


if __name__ == "__main__":
    setup_logging()
    parser = argparse.ArgumentParser(
        description="Сбросить уровни пользователей и уведомить их (для поддержки)"
    )
    parser.add_argument(
        "--all",
        dest="all_users",
        action="store_true",
        help="сбросить уровни у всех, не проверяя результаты тестов",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="показать, кого затронет, ничего не меняя",
    )
    arguments = parser.parse_args()
    raise SystemExit(
        asyncio.run(main(only_wrong=not arguments.all_users, dry_run=arguments.dry_run))
    )
