"""Forecasting helpers for analytics charts.

Pure functions: linear regression forecast, moving average, forecast date generation.
No Streamlit or database dependencies.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd


def linear_forecast(
    dates: pd.Series,
    values: List[float],
    forecast_days: int = 5,
) -> Optional[List[Dict[str, Any]]]:
    """Linear regression forecast with ±1 std dev confidence band.

    Returns None if fewer than 7 data points (not enough for reliable forecast).
    Each entry: {"date": Timestamp, "value": float, "upper": float, "lower": float}
    """
    if len(values) < 7:
        return None

    x = np.arange(len(values), dtype=float)
    y = np.array(values, dtype=float)

    coeffs = np.polyfit(x, y, 1)
    slope, intercept = coeffs[0], coeffs[1]

    residuals = y - (slope * x + intercept)
    std_err = float(np.std(residuals))
    # Ensure minimum uncertainty even for perfectly linear data
    std_err = max(std_err, 1.0)

    # Handle both Series and DatetimeIndex
    if isinstance(dates, pd.DatetimeIndex):
        last_date = pd.Timestamp(dates[-1])
    else:
        last_date = pd.Timestamp(dates.iloc[-1])
    forecast_dates = generate_forecast_dates(last_date, forecast_days)

    result: List[Dict[str, Any]] = []
    for i, fdate in enumerate(forecast_dates):
        future_x = len(values) + i
        value = slope * future_x + intercept
        band = std_err * (1 + i * 0.15)
        result.append(
            {
                "date": fdate,
                "value": float(value),
                "upper": float(value + band),
                "lower": float(max(0, value - band)),
            }
        )

    return result


def moving_average(
    values: List[float],
    window: int = 7,
) -> List[float]:
    """Compute simple moving average. Returns same length as input.

    Leading entries (before enough data for the window) are NaN.
    """
    if window <= 0:
        return list(values)
    if window == 1:
        return list(values)

    result: List[float] = []
    for i in range(len(values)):
        if i < window - 1:
            result.append(float("nan"))
        else:
            window_vals = values[i - window + 1 : i + 1]
            result.append(sum(window_vals) / len(window_vals))
    return result


def generate_forecast_dates(
    last_date: pd.Timestamp,
    forecast_days: int,
) -> List[pd.Timestamp]:
    """Generate consecutive dates starting the day after last_date."""
    return [last_date + timedelta(days=i + 1) for i in range(forecast_days)]


def calculate_forecast_days(analysis_period: str, data_points: int = 0) -> int:
    """Calculate forecast length based on selected analysis period.

    Forecast should extend beyond the selected period to be useful:
    - "This Week" / "Last Week" / "Last 7 Days" → forecast 7 days ahead
    - "This Month" / "Last Month" → forecast 30 days ahead
    - "Last 30 Days" → forecast 30 days ahead
    - "Custom" → forecast 30 days ahead (default for custom ranges)

    Minimum 7 data points required; if fewer, uses minimum forecast of 3 days.
    """
    if data_points < 7:
        return 3  # Fallback for short periods

    period_map = {
        "this_week": 7,
        "last_week": 7,
        "last_7_days": 7,
        "this_month": 30,
        "last_month": 30,
        "last_30_days": 30,
        "custom": 30,
    }

    period_key = analysis_period.lower().replace(" ", "_")
    return period_map.get(period_key, 30)
