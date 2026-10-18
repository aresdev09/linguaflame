"""Онбординг: /start, выбор родного языка и часового пояса."""

import logging
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards import (
    LANGUAGE_CALLBACK_PREFIX,
    TIMEZONE_CALLBACK_PREFIX,
    language_kb,
    timezone_kb,
)
from bot.locales import DEFAULT_LANGUAGE, SUPPORTED_LANGUAGES, t
from bot.models import User
from bot.repositories import UserRepo
from bot.states import OnboardingStates

logger = logging.getLogger(__name__)

router = Router(name="start")


@router.message(Command("start"))
async def start_command(
    message: Message,
    state: FSMContext,
    user: User,
    is_new_user: bool,
) -> None:
    """Приветствие: новому пользователю — онбординг, старому — настройки."""
    lang = DEFAULT_LANGUAGE if is_new_user else user.native_language
    name = message.from_user.first_name or t("common.friend", lang)

    if not is_new_user:
        await state.clear()
        await message.answer(
            t(
                "start.already_configured",
                lang,
                name=name,
                language=t(f"language.{user.native_language}", lang),
                timezone=user.timezone,
            )
        )
        await message.answer(t("start.commands_hint", lang))
        return

    await state.set_state(OnboardingStates.choose_language)
    await message.answer(t("start.greeting", lang, name=name))
    await message.answer(
        t("start.choose_language", lang), reply_markup=language_kb(lang)
    )


@router.callback_query(F.data.startswith(LANGUAGE_CALLBACK_PREFIX))
async def choose_language(
    callback: CallbackQuery,
    state: FSMContext,
    user: User,
    session: AsyncSession,
) -> None:
    """Сохраняет родной язык и просит выбрать часовой пояс."""
    lang = callback.data.removeprefix(LANGUAGE_CALLBACK_PREFIX)
    if lang not in SUPPORTED_LANGUAGES:
        await callback.answer(t("common.language_not_supported", user.native_language))
        return

    await UserRepo(session).update_profile(user.id, native_language=lang)
    await callback.answer()
    if callback.message is None:
        return

    await state.set_state(OnboardingStates.choose_timezone)
    await callback.message.answer(
        t("start.language_saved", lang, language=t(f"language.{lang}", lang))
    )
    await callback.message.answer(
        t("start.choose_timezone", lang), reply_markup=timezone_kb(lang)
    )


@router.callback_query(F.data.startswith(TIMEZONE_CALLBACK_PREFIX))
async def choose_timezone(
    callback: CallbackQuery,
    state: FSMContext,
    user: User,
    session: AsyncSession,
) -> None:
    """Сохраняет часовой пояс и завершает онбординг."""
    timezone = callback.data.removeprefix(TIMEZONE_CALLBACK_PREFIX)
    try:
        ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, ValueError):
        await callback.answer(t("common.timezone_invalid", user.native_language))
        return

    await UserRepo(session).update_profile(user.id, timezone=timezone)
    await callback.answer()
    if callback.message is None:
        return

    lang = user.native_language
    await state.clear()
    await callback.message.answer(t("start.timezone_saved", lang, timezone=timezone))
    await callback.message.answer(t("start.commands_hint", lang))