"""Shared forecast orchestration for report and analytics consumers."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Sequence

import pandas as pd

from tabs.forecasting import linear_forecast

# Days of history the model is fitted on. The window deliberately crosses month
# boundaries: fitting on the current month alone leaves the first ten days of a
# month with too few points to read a weekday pattern, which is where month-end
# forecasts were least accurate.
DEFAULT_TRAILING_DAYS = 56


def calculate_month_end_forecast(
    dates: Sequence[Any] | pd.Series,
    values: Sequence[float],
    *,
    as_of_date: date,
    actual_total: float | None = None,
    trailing_days: int = DEFAULT_TRAILING_DAYS,
) -> dict[str, Any]:
    """Project month-end sales from data available through ``as_of_date``.

    Two distinct windows are used:

    * the **model window** — a trailing ``trailing_days`` span ending at
      ``as_of_date``, which may reach back into previous months, used only to fit
      the weighted forecast;
    * the **month window** — the current month up to ``as_of_date``, which
      supplies the month-to-date actual the forecast is added to.

    ``as_of_date`` must be the last date the caller actually has data for, not
    today's date; days between the two would otherwise be silently dropped from
    both the actual and the forecast.

    The weighted analytics model is used when at least three daily observations
    are available. Sparse histories fall back to a run rate over days that
    actually traded so the Report tab can still produce a useful result.
    """
    # Reset both indexes before pairing: a filtered Series carries its old index
    # and pandas would align it against a list's 0..n index, mismatching rows.
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

    as_of = pd.Timestamp(as_of_date).normalize()
    month_start = as_of.replace(day=1)

    if not history.empty:
        history["date"] = history["date"].dt.normalize()
        history["value"] = history["value"].clip(lower=0)
        history = (
            history.groupby("date", as_index=False)["value"]
            .sum()
            .sort_values("date")
            .reset_index(drop=True)
        )

    window_start = as_of - pd.Timedelta(days=max(1, int(trailing_days)) - 1)
    model_history = (
        history[(history["date"] >= window_start) & (history["date"] <= as_of)]
        .reset_index(drop=True)
        .copy()
    )
    month_history = (
        history[(history["date"] >= month_start) & (history["date"] <= as_of)]
        .reset_index(drop=True)
        .copy()
    )

    if as_of.month == 12:
        next_month = pd.Timestamp(date(as_of.year + 1, 1, 1))
    else:
        next_month = pd.Timestamp(date(as_of.year, as_of.month + 1, 1))

    days_in_month = int((next_month - timedelta(days=1)).day)
    remaining_days = max(0, int((next_month - as_of).days) - 1)
    observed_total = float(month_history["value"].sum())
    month_actual = max(0.0, float(actual_total if actual_total is not None else observed_total))

    # Days that actually traded, so closed days do not deflate the run rate.
    active_days = int((month_history["value"] > 0).sum())
    covered_days = int(month_history["date"].nunique())
    elapsed_days = int(as_of.day)

    # Only trust the trading-day count when the history covers every elapsed day.
    # A gap could be a closure or simply an upload that has not happened yet, and
    # the two are indistinguishable here; dividing a full month-to-date figure by
    # a handful of uploaded days would wildly overstate the run rate.
    history_is_complete = covered_days >= elapsed_days
    rate_days = active_days if (history_is_complete and active_days > 0) else elapsed_days

    forecast = linear_forecast(
        model_history["date"],
        model_history["value"].tolist(),
        forecast_days=remaining_days,
        forecast_after_date=as_of,
    )

    method = "weighted"
    if forecast is None and remaining_days > 0:
        method = "run_rate"
        daily_run_rate = month_actual / max(1, rate_days)
        forecast = [
            {
                "date": as_of + timedelta(days=index),
                "value": daily_run_rate,
                "upper": daily_run_rate,
                "lower": daily_run_rate,
                "metadata": {
                    "model_label": "Trading-day run-rate fallback",
                    "data_points": len(model_history),
                    "reliability": "Low",
                },
            }
            for index in range(1, remaining_days + 1)
        ]

    forecast_values = [float(item.get("value", 0) or 0) for item in (forecast or [])]
    projected_total = month_actual + sum(forecast_values)

    return {
        "actual_total": month_actual,
        "days_in_month": days_in_month,
        "elapsed_days": elapsed_days,
        "active_days": active_days,
        "covered_days": covered_days,
        "rate_days": rate_days,
        "remaining_days": remaining_days,
        "as_of_date": as_of.date(),
        "forecast": forecast or [],
        "forecast_total": projected_total,
        "forecast_future_sales": sum(forecast_values),
        "method": method if remaining_days > 0 else "actual",
        "history_points": len(month_history),
        "model_points": len(model_history),
        "trailing_days": int(trailing_days),
    }
