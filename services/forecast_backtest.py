"""Backtesting harness for month-end sales forecasts.

Answers one question: if we had stood at each day of a past month and forecast
that month's close, how wrong would we have been?

This exists because a forecast change once shipped on the strength of a
comparison between two variants of the same model, without either being measured
against a plain run-rate baseline. It turned out to be worse than the baseline.
Any future change to the model should be run through :func:`compare_strategies`
first, and should beat ``run_rate`` on both mean and worst-case error.

Pure functions over a daily series — no Streamlit, no database.
"""

from __future__ import annotations

import calendar
from datetime import date, timedelta
from typing import Any, Callable, Sequence

import numpy as np
import pandas as pd

from services.forecast_service import DEFAULT_TRAILING_DAYS, calculate_month_end_forecast

# A strategy takes (history, as_of, month_to_date_actual) and returns a
# projected month-end total.
Strategy = Callable[[pd.DataFrame, date, float], float]


def _to_frame(
    dates: Sequence[Any] | pd.Series,
    values: Sequence[float],
) -> pd.DataFrame:
    """Normalise inputs to a sorted one-row-per-day frame."""
    frame = pd.DataFrame(
        {
            "date": pd.to_datetime(
                pd.Series(dates).reset_index(drop=True), errors="coerce"
            ),
            "value": pd.to_numeric(
                pd.Series(values).reset_index(drop=True), errors="coerce"
            ),
        }
    ).dropna(subset=["date", "value"])

    if frame.empty:
        return pd.DataFrame(columns=["date", "value"])

    frame["date"] = frame["date"].dt.normalize()
    frame["value"] = frame["value"].clip(lower=0)

    return (
        frame.groupby("date", as_index=False)["value"]
        .sum()
        .sort_values("date")
        .reset_index(drop=True)
    )


def _window(frame: pd.DataFrame, start: date, end: date) -> pd.DataFrame:
    mask = (frame["date"] >= pd.Timestamp(start)) & (frame["date"] <= pd.Timestamp(end))
    return frame[mask].reset_index(drop=True)


def _remaining_days(as_of: date) -> list[date]:
    days_in_month = calendar.monthrange(as_of.year, as_of.month)[1]
    return [
        date(as_of.year, as_of.month, day)
        for day in range(as_of.day + 1, days_in_month + 1)
    ]


# ---------------------------------------------------------------- strategies
def strategy_run_rate(history: pd.DataFrame, as_of: date, mtd: float) -> float:
    """Straight-line baseline: month-to-date divided by elapsed days."""
    days_in_month = calendar.monthrange(as_of.year, as_of.month)[1]
    return (mtd / max(1, as_of.day)) * days_in_month


def strategy_weekday_weekend(
    history: pd.DataFrame,
    as_of: date,
    mtd: float,
    lookback: int = DEFAULT_TRAILING_DAYS,
    weekend: frozenset[int] = frozenset({4, 5, 6}),
) -> float:
    """Two buckets: an average Mon-Thu day and an average Fri-Sun day."""
    window = _window(history, as_of - timedelta(days=lookback - 1), as_of)
    window = window[window["value"] > 0]

    if window.empty:
        return strategy_run_rate(history, as_of, mtd)

    is_weekend = window["date"].dt.weekday.isin(weekend)
    weekend_avg = float(window[is_weekend]["value"].mean() or 0)
    weekday_avg = float(window[~is_weekend]["value"].mean() or 0)

    return mtd + sum(
        weekend_avg if day.weekday() in weekend else weekday_avg
        for day in _remaining_days(as_of)
    )


def strategy_current_model(
    history: pd.DataFrame,
    as_of: date,
    mtd: float,
) -> float:
    """Whatever the application currently ships."""
    return float(
        calculate_month_end_forecast(
            history["date"],
            history["value"].tolist(),
            as_of_date=as_of,
            actual_total=mtd,
        )["forecast_total"]
    )


DEFAULT_STRATEGIES: dict[str, Strategy] = {
    "run_rate": strategy_run_rate,
    "weekday_weekend": strategy_weekday_weekend,
    "current_model": strategy_current_model,
}


# ----------------------------------------------------------------- backtest
def backtest_month(
    dates: Sequence[Any] | pd.Series,
    values: Sequence[float],
    *,
    year: int,
    month: int,
    strategy: Strategy,
    first_day: int = 5,
    last_day: int | None = None,
) -> dict[str, Any]:
    """Score one strategy over one month.

    Forecasts that month's close from each day in turn and compares against what
    the month actually closed at. Returns ``available: False`` when the month has
    no usable actuals.
    """
    frame = _to_frame(dates, values)
    days_in_month = calendar.monthrange(year, month)[1]
    stop = min(last_day or days_in_month - 1, days_in_month - 1)

    actual = float(
        _window(frame, date(year, month, 1), date(year, month, days_in_month))[
            "value"
        ].sum()
    )

    if actual <= 0:
        return {"available": False, "reason": "No actual sales recorded for this month."}

    errors: list[dict[str, Any]] = []

    for day in range(first_day, stop + 1):
        as_of = date(year, month, day)
        history = _window(frame, date(year, month, 1) - timedelta(days=365), as_of)

        if history.empty:
            continue

        mtd = float(_window(frame, date(year, month, 1), as_of)["value"].sum())

        try:
            predicted = float(strategy(history, as_of, mtd))
        except Exception:  # a strategy that blows up simply does not score
            continue

        errors.append(
            {
                "as_of": as_of,
                "predicted": predicted,
                "actual": actual,
                "error_pct": (predicted - actual) / actual * 100,
            }
        )

    if not errors:
        return {"available": False, "reason": "No forecastable days in this month."}

    abs_errors = [abs(row["error_pct"]) for row in errors]

    return {
        "available": True,
        "year": year,
        "month": month,
        "actual": actual,
        "days_scored": len(errors),
        "mape": float(np.mean(abs_errors)),
        "median_abs_error": float(np.median(abs_errors)),
        "p90_abs_error": float(np.percentile(abs_errors, 90)),
        "worst_abs_error": float(max(abs_errors)),
        "bias": float(np.mean([row["error_pct"] for row in errors])),
        "detail": errors,
    }


def compare_strategies(
    dates: Sequence[Any] | pd.Series,
    values: Sequence[float],
    *,
    months: Sequence[tuple[int, int]],
    strategies: dict[str, Strategy] | None = None,
    first_day: int = 5,
) -> dict[str, Any]:
    """Score several strategies over several months and rank them.

    ``months`` is a sequence of ``(year, month)`` pairs. The ranking is by mean
    absolute percentage error across every scored day of every month.
    """
    strategies = strategies or DEFAULT_STRATEGIES
    summary: dict[str, Any] = {}

    for name, strategy in strategies.items():
        abs_errors: list[float] = []
        signed: list[float] = []
        months_scored = 0

        for year, month in months:
            result = backtest_month(
                dates,
                values,
                year=year,
                month=month,
                strategy=strategy,
                first_day=first_day,
            )

            if not result.get("available"):
                continue

            months_scored += 1
            abs_errors.extend(abs(row["error_pct"]) for row in result["detail"])
            signed.extend(row["error_pct"] for row in result["detail"])

        if not abs_errors:
            summary[name] = {"available": False}
            continue

        summary[name] = {
            "available": True,
            "months_scored": months_scored,
            "days_scored": len(abs_errors),
            "mape": float(np.mean(abs_errors)),
            "p90_abs_error": float(np.percentile(abs_errors, 90)),
            "worst_abs_error": float(max(abs_errors)),
            "bias": float(np.mean(signed)),
        }

    ranked = sorted(
        (name for name, row in summary.items() if row.get("available")),
        key=lambda name: summary[name]["mape"],
    )

    return {
        "strategies": summary,
        "ranked": ranked,
        "best": ranked[0] if ranked else None,
    }


def format_comparison(comparison: dict[str, Any]) -> str:
    """Render :func:`compare_strategies` output as a plain-text table."""
    lines = [
        f"{'strategy':<22}{'MAPE':>9}{'p90':>9}{'worst':>9}{'bias':>9}{'days':>7}",
        "-" * 65,
    ]

    for name in comparison["ranked"]:
        row = comparison["strategies"][name]
        lines.append(
            f"{name:<22}{row['mape']:>8.2f}%{row['p90_abs_error']:>8.2f}%"
            f"{row['worst_abs_error']:>8.2f}%{row['bias']:>+8.2f}%{row['days_scored']:>7}"
        )

    if comparison["best"]:
        lines.append("")
        lines.append(f"best: {comparison['best']}")

    return "\n".join(lines)
