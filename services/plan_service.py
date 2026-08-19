"""Suggested plan vs actual plan comparison.

Turns a monthly sales target into a day-by-day plan shaped by the same weekday
pattern the forecast uses, then scores actual trading against it.

A flat ``target / days_in_month`` plan is misleading for a restaurant: a Monday
and a Saturday are not interchangeable days. Shaping the plan by weekday means
"behind plan" reflects genuine underperformance rather than which days of the
week happen to have passed.

Three series are produced for the month:

* **plan** — the target, distributed across every day by weekday weight;
* **actual** — what really traded, for days up to the as-of date;
* **suggested** — what the forecast expects for the days still to come.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Sequence

import pandas as pd

from services.forecast_service import DEFAULT_TRAILING_DAYS, calculate_month_end_forecast
from tabs.forecasting import build_weekday_shape


def _month_bounds(as_of: pd.Timestamp) -> tuple[pd.Timestamp, pd.Timestamp]:
    """Return the first and last day of the month containing ``as_of``."""
    month_start = as_of.replace(day=1)

    if as_of.month == 12:
        next_month = pd.Timestamp(date(as_of.year + 1, 1, 1))
    else:
        next_month = pd.Timestamp(date(as_of.year, as_of.month + 1, 1))

    return month_start, next_month - pd.Timedelta(days=1)


def build_plan_vs_actual(
    dates: Sequence[Any] | pd.Series,
    values: Sequence[float],
    *,
    as_of_date: date,
    month_target: float,
    actual_total: float | None = None,
    trailing_days: int = DEFAULT_TRAILING_DAYS,
    forecast_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compare a weekday-shaped target plan against actuals and the forecast.

    ``as_of_date`` must be the last date with data. Returns ``available: False``
    when no usable target is set, so callers can degrade gracefully.
    """
    as_of = pd.Timestamp(as_of_date).normalize()
    month_start, month_end = _month_bounds(as_of)
    target = float(month_target or 0)

    result = forecast_result or calculate_month_end_forecast(
        dates,
        values,
        as_of_date=as_of_date,
        actual_total=actual_total,
        trailing_days=trailing_days,
    )

    # Reset both indexes before pairing (see forecast_service for the rationale).
    history = pd.DataFrame(
        {
            "date": pd.to_datetime(
                pd.Series(dates).reset_index(drop=True), errors="coerce"
            ),
            "value": pd.to_numeric(
                pd.Series(values).reset_index(drop=True), errors="coerce"
            ),
        }
    ).dropna(subset=["date", "value"])

    if not history.empty:
        history["date"] = history["date"].dt.normalize()
        history["value"] = history["value"].clip(lower=0)
        history = history.groupby("date", as_index=False)["value"].sum()

    actual_by_date = dict(zip(history.get("date", []), history.get("value", [])))

    # Weekday weights come from the same trailing window the forecast is fitted on.
    window_start = as_of - pd.Timedelta(days=max(1, int(trailing_days)) - 1)
    model_history = (
        history[(history["date"] >= window_start) & (history["date"] <= as_of)]
        .reset_index(drop=True)
        if not history.empty
        else history
    )
    shape = (
        build_weekday_shape(model_history["date"], model_history["value"].tolist())
        if not model_history.empty
        else {}
    )

    forecast_by_date = {
        pd.Timestamp(item["date"]).normalize(): float(item.get("value", 0) or 0)
        for item in result.get("forecast", [])
    }

    month_days = pd.date_range(month_start, month_end, freq="D")
    weight = {day: float(shape.get(int(day.weekday()), 1.0)) for day in month_days}
    shape_total = sum(weight.values())

    if target <= 0 or shape_total <= 0:
        return {
            "available": False,
            "reason": (
                "No monthly target is set for this scope, so a plan comparison "
                "cannot be produced."
            ),
            "month_target": target,
            "as_of_date": as_of.date(),
        }

    daily: list[dict[str, Any]] = []
    plan_to_date = 0.0
    actual_to_date = 0.0

    for day in month_days:
        plan_value = target * weight[day] / shape_total
        is_elapsed = day <= as_of
        actual_value = float(actual_by_date.get(day, 0.0)) if is_elapsed else None
        suggested = None if is_elapsed else forecast_by_date.get(day)

        if is_elapsed:
            plan_to_date += plan_value
            actual_to_date += actual_value or 0.0

        daily.append(
            {
                "date": day.date(),
                "weekday": day.strftime("%a"),
                "phase": "actual" if is_elapsed else "forecast",
                "plan": plan_value,
                "actual": actual_value,
                "suggested": suggested,
                "variance": (actual_value - plan_value) if is_elapsed else None,
            }
        )

    # Prefer the caller's month-to-date figure when supplied; it is the audited one.
    if actual_total is not None:
        actual_to_date = float(actual_total)

    forward_days = [day for day in month_days if day > as_of]
    forward_weight_total = sum(weight[day] for day in forward_days)
    gap = target - actual_to_date

    catchup: list[dict[str, Any]] = []
    for day in forward_days:
        required = (
            max(0.0, gap) * weight[day] / forward_weight_total
            if forward_weight_total > 0
            else 0.0
        )
        catchup.append(
            {
                "date": day.date(),
                "weekday": day.strftime("%a"),
                "required": required,
                "suggested": forecast_by_date.get(day, 0.0),
                "shortfall": required - forecast_by_date.get(day, 0.0),
            }
        )

    variance_to_date = actual_to_date - plan_to_date
    forecast_close = float(result.get("forecast_total", 0.0))
    suggested_forward = float(result.get("forecast_future_sales", 0.0))
    remaining = len(forward_days)

    if plan_to_date > 0:
        variance_pct = (variance_to_date / plan_to_date) * 100
    else:
        variance_pct = 0.0

    if variance_pct >= 2:
        status = "ahead"
    elif variance_pct <= -2:
        status = "behind"
    else:
        status = "on_track"

    required_forward_daily = (max(0.0, gap) / remaining) if remaining > 0 else 0.0
    suggested_forward_daily = (suggested_forward / remaining) if remaining > 0 else 0.0

    return {
        "available": True,
        "month_target": target,
        "as_of_date": as_of.date(),
        "days_in_month": len(month_days),
        "remaining_days": remaining,
        "weekday_shape": shape,
        "daily": daily,
        "catchup": catchup,
        "plan_to_date": plan_to_date,
        "actual_to_date": actual_to_date,
        "variance_to_date": variance_to_date,
        "variance_pct": variance_pct,
        "status": status,
        "forecast_close": forecast_close,
        "forecast_vs_target": forecast_close - target,
        "forecast_target_pct": (forecast_close / target * 100) if target > 0 else None,
        "gap_to_target": gap,
        "required_forward_daily": required_forward_daily,
        "suggested_forward_daily": suggested_forward_daily,
        "required_lift_pct": (
            ((required_forward_daily / suggested_forward_daily) - 1) * 100
            if suggested_forward_daily > 0
            else None
        ),
        "shape_is_flat": not shape,
    }
