"""Состояния FSM-диалогов бота.

Здесь собраны все группы состояний, даже если хендлеры команды
появятся позже.
"""

from aiogram.fsm.state import State, StatesGroup


class OnboardingStates(StatesGroup):
    """Первый запуск: выбор родного языка и часового пояса."""

    choose_language = State()
    choose_timezone = State()


class QuizStates(StatesGroup):
    """Диалог квиза."""

    answering = State()


class GrammarStates(StatesGroup):
    """Пошаговый урок грамматики."""

    waiting_plan = State()
    in_lesson = State()
    final_test = State()


class FreeChatStates(StatesGroup):
    """Свободный разговор."""

    chatting = State()


class LevelTestStates(StatesGroup):
    """Тест на определение уровня."""

    answering = State()


class EssayStates(StatesGroup):
    """Проверка эссе."""

    waiting_text = State()
