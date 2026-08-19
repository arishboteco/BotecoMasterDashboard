"""Tests for the forecast backtesting harness.

The regression guard here is deliberate: a previous model change shipped without
ever being measured against a straight-line baseline, and turned out to be worse
than it. These tests fail if that happens again.
"""

from datetime import date, timedelta

import pytest

from services.forecast_backtest import (
    DEFAULT_STRATEGIES,
    backtest_month,
    compare_strategies,
    format_comparison,
    strategy_run_rate,
)


def _weekday_shaped_history(start: date, days: int) -> tuple[list[str], list[float]]:
    """Strong, stable weekly pattern — Mondays quiet, weekends busy."""
    by_weekday = {0: 60000, 1: 80000, 2: 85000, 3: 90000, 4: 120000, 5: 160000, 6: 150000}
    dates, values = [], []

    for index in range(days):
        day = start + timedelta(days=index)
        dates.append(day.isoformat())
        values.append(float(by_weekday[day.weekday()]))

    return dates, values


def test_backtest_scores_every_day_of_the_month() -> None:
    dates, values = _weekday_shaped_history(date(2026, 4, 1), 122)  # Apr-Jul

    result = backtest_month(
        dates, values, year=2026, month=7, strategy=strategy_run_rate, first_day=5
    )

    assert result["available"]
    assert result["days_scored"] == 26  # days 5..30
    assert result["actual"] == pytest.approx(sum(values[-31:]))
    assert result["mape"] >= 0


def test_backtest_reports_unavailable_for_a_month_with_no_sales() -> None:
    dates, values = _weekday_shaped_history(date(2026, 6, 1), 60)

    result = backtest_month(
        dates, values, year=2026, month=1, strategy=strategy_run_rate
    )

    assert not result["available"]


def test_perfect_pattern_is_forecast_almost_exactly() -> None:
    """With a repeating week and no noise, the model should be near-perfect."""
    dates, values = _weekday_shaped_history(date(2026, 4, 1), 122)

    result = backtest_month(
        dates,
        values,
        year=2026,
        month=7,
        strategy=DEFAULT_STRATEGIES["current_model"],
        first_day=8,
    )

    assert result["available"]
    assert result["mape"] < 1.0


def test_current_model_beats_the_run_rate_baseline() -> None:
    """Regression guard: never ship a model that loses to a straight line."""
    dates, values = _weekday_shaped_history(date(2026, 3, 1), 153)  # Mar-Jul

    comparison = compare_strategies(
        dates, values, months=[(2026, 5), (2026, 6), (2026, 7)]
    )

    current = comparison["strategies"]["current_model"]
    baseline = comparison["strategies"]["run_rate"]

    assert current["available"] and baseline["available"]
    assert current["mape"] < baseline["mape"]
    assert current["worst_abs_error"] <= baseline["worst_abs_error"]
    assert comparison["best"] == "current_model"


def test_current_model_beats_the_weekday_weekend_split() -> None:
    """Per-weekday averaging should beat a two-bucket weekday/weekend split."""
    dates, values = _weekday_shaped_history(date(2026, 3, 1), 153)

    comparison = compare_strategies(
        dates, values, months=[(2026, 5), (2026, 6), (2026, 7)]
    )

    assert (
        comparison["strategies"]["current_model"]["mape"]
        < comparison["strategies"]["weekday_weekend"]["mape"]
    )


def test_noisy_history_still_ranks_the_model_first() -> None:
    """Add day-to-day noise so the win is not an artefact of a clean fixture."""
    import random

    rng = random.Random(20260819)
    dates, values = _weekday_shaped_history(date(2026, 3, 1), 153)
    noisy = [v * rng.uniform(0.80, 1.20) for v in values]

    comparison = compare_strategies(
        dates, noisy, months=[(2026, 5), (2026, 6), (2026, 7)]
    )

    assert comparison["best"] == "current_model"


def test_format_comparison_renders_a_ranked_table() -> None:
    dates, values = _weekday_shaped_history(date(2026, 3, 1), 153)

    text = format_comparison(
        compare_strategies(dates, values, months=[(2026, 6), (2026, 7)])
    )

    assert "MAPE" in text
    assert "current_model" in text
    assert "best:" in text
