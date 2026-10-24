"""Тесты подсчёта результата теста уровня (задача 8.12)."""

import random

from bot.config import CONSISTENCY_LIFT_MIN_PERCENT, LEVEL_TEST_DISTRIBUTION, LEVELS
from bot.services.level_test import (
    LevelAnswer,
    compute_level_test_result,
    level_from_percent,
    score_answer,
)


def _make_answers(
    *,
    is_correct: object,
    answer_time_sec: int,
) -> list[LevelAnswer]:
    """50 ответов по конфигу распределения; is_correct — функция или bool."""
    answers: list[LevelAnswer] = []
    for level, total in LEVEL_TEST_DISTRIBUTION.items():
        for index in range(total):
            correct = is_correct(level, index) if callable(is_correct) else bool(is_correct)
            answers.append(
                LevelAnswer(
                    level=level,
                    kind="grammar" if index % 2 == 0 else "vocabulary",
                    is_correct=correct,
                    answer_time_sec=answer_time_sec,
                )
            )
    return answers


def test_all_correct_and_fast_gives_c2() -> None:
    result = compute_level_test_result(_make_answers(is_correct=True, answer_time_sec=1))

    assert result.level == "C2"
    assert result.correct_count == 50
    assert result.total_count == 50
    assert result.percent > 88


def test_all_correct_at_comfortable_speed_gives_c2() -> None:
    result = compute_level_test_result(_make_answers(is_correct=True, answer_time_sec=5))

    assert result.level == "C2"
    assert result.percent == 100.0


def test_all_wrong_gives_a1() -> None:
    result = compute_level_test_result(_make_answers(is_correct=False, answer_time_sec=5))

    assert result.level == "A1"
    assert result.correct_count == 0
    assert result.percent == 0.0


def test_fast_random_clicks_never_give_high_levels() -> None:
    # Ключевая регрессия: раньше подъём согласованности выдавал C2 примерно
    # в 7% прогонов чистых случайных кликов. Проверяем на множестве seed:
    # C1/C2 не появляются, редкая удача может дотянуть максимум до B2.
    for seed in range(2000):
        rng = random.Random(seed)

        # rng в значении по умолчанию — ruff требует явной привязки в цикле.
        def random_correct(level: str, index: int, _rng: random.Random = rng) -> bool:
            return _rng.random() < 1 / 3

        result = compute_level_test_result(
            _make_answers(is_correct=random_correct, answer_time_sec=1)
        )
        assert LEVELS.index(result.level) < LEVELS.index("C1"), (
            f"seed {seed}: случайные клики дали {result.level} ({result.percent}%)"
        )


def test_speed_bonus_rewards_fast_answers() -> None:
    fast = compute_level_test_result(_make_answers(is_correct=True, answer_time_sec=5))
    slow = compute_level_test_result(_make_answers(is_correct=True, answer_time_sec=61))

    assert fast.percent > slow.percent
    assert fast.percent == 100.0
    assert slow.percent < 100.0


def test_guessing_rule_applies_from_b1() -> None:
    # A1: быстрый ответ даёт бонус, B1: меньше 2 секунд — угадывание.
    assert score_answer("A1", is_correct=True, answer_time_sec=1) == 1.1
    assert score_answer("B1", is_correct=True, answer_time_sec=1) == 3.0
    assert score_answer("B2", is_correct=True, answer_time_sec=2) == 4.4
    # Очень медленный ответ бонуса не получает.
    assert score_answer("C1", is_correct=True, answer_time_sec=61) == 5.0


def test_lucky_c2_answers_do_not_make_a_beginner_c2() -> None:
    # 6 из 10 C2-вопросов угаданы, но общий результат низкий: уровень решают пороги.
    def only_c2_correct(level: str, index: int) -> bool:
        return level == "C2" and index < 6

    result = compute_level_test_result(_make_answers(is_correct=only_c2_correct, answer_time_sec=5))

    assert result.percent == 20.0
    assert result.level == "A2"


def test_consistency_does_not_lift_below_lift_threshold() -> None:
    # Верно только всё сложное, общий процент в полосе B2 — подъём не работает.
    def only_high_levels_correct(level: str, index: int) -> bool:
        return level in {"C1", "C2"}

    result = compute_level_test_result(
        _make_answers(is_correct=only_high_levels_correct, answer_time_sec=5)
    )

    assert result.percent < CONSISTENCY_LIFT_MIN_PERCENT
    assert result.level == "B2"


def test_consistency_lift_works_near_top() -> None:
    # Пользователь почти на пороге C2, C2-вопросы отвечает верно: подъём на один уровень.
    def near_top(level: str, index: int) -> bool:
        if level == "A1":
            return index < 2
        if level == "C1":
            return index < 7
        if level == "C2":
            return index < 7
        return True

    result = compute_level_test_result(_make_answers(is_correct=near_top, answer_time_sec=5))

    assert result.percent > CONSISTENCY_LIFT_MIN_PERCENT
    assert result.percent < 88
    assert result.level == "C2"


def test_level_thresholds() -> None:
    assert level_from_percent(0) == "A1"
    assert level_from_percent(14.9) == "A1"
    assert level_from_percent(15) == "A2"
    assert level_from_percent(29.9) == "A2"
    assert level_from_percent(30) == "B1"
    assert level_from_percent(50) == "B2"
    assert level_from_percent(70) == "C1"
    assert level_from_percent(87.9) == "C1"
    assert level_from_percent(95) == "C2"
