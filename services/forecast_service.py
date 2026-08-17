"""Shared forecast orchestration for report and analytics consumers."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Sequence

import pandas as pd

from tabs.forecasting import linear_forecast


def calculate_month_end_forecast(
    dates: Sequence[Any] | pd.Series,
    values: Sequence[float],
    *,
    as_of_date: date,
    actual_total: float | None = None,
) -> dict[str, Any]:
    """Project month-end sales from data available through ``as_of_date``.

    The weighted analytics model is used when at least three daily observations
    are available. Sparse histories fall back to a calendar-day run rate so the
    Report tab can still produce a useful result.
    """
    history = pd.DataFrame(
        {
            "date": pd.to_datetime(pd.Series(dates), errors="coerce"),
            "value": pd.to_numeric(pd.Series(values), errors="coerce"),
        }
    ).dropna(subset=["date", "value"])

    as_of = pd.Timestamp(as_of_date).normalize()
    month_start = as_of.replace(day=1)
    history["date"] = history["date"].dt.normalize()
    history["value"] = history["value"].clip(lower=0)
    history = history[
        (history["date"] >= month_start) & (history["date"] <= as_of)
    ].copy()
    history = (
        history.groupby("date", as_index=False)["value"]
        .sum()
        .sort_values("date")
        .reset_index(drop=True)
    )

    if as_of.month == 12:
        next_month = pd.Timestamp(date(as_of.year + 1, 1, 1))
    else:
        next_month = pd.Timestamp(date(as_of.year, as_of.month + 1, 1))

    days_in_month = int((next_month - timedelta(days=1)).day)
    remaining_days = max(0, int((next_month - as_of).days) - 1)
    observed_total = float(history["value"].sum())
    month_actual = max(0.0, float(actual_total if actual_total is not None else observed_total))

    forecast = linear_forecast(
        history["date"],
        history["value"].tolist(),
        forecast_days=remaining_days,
        forecast_after_date=as_of,
    )

    method = "weighted"
    if forecast is None and remaining_days > 0:
        method = "run_rate"
        daily_run_rate = month_actual / max(1, int(as_of.day))
        forecast = [
            {
                "date": as_of + timedelta(days=index),
                "value": daily_run_rate,
                "upper": daily_run_rate,
                "lower": daily_run_rate,
                "metadata": {
                    "model_label": "Calendar run-rate fallback",
                    "data_points": len(history),
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
        "elapsed_days": int(as_of.day),
        "remaining_days": remaining_days,
        "forecast": forecast or [],
        "forecast_total": projected_total,
        "forecast_future_sales": sum(forecast_values),
        "method": method if remaining_days > 0 else "actual",
        "history_points": len(history),
    }
