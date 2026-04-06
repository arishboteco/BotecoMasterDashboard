"""Forecasting helpers for analytics charts.

Pure functions: exponential smoothing forecast, moving average, forecast date generation.
No Streamlit or database dependencies.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd


def linear_forecast(
    dates: pd.Series,
    values: List[float],
    forecast_days: int = 5,
) -> Optional[List[Dict[str, Any]]]:
    """Forecast future values using exponential smoothing + weekday patterns.

    Approach (based on restaurant forecasting research):
    1. Compute a base forecast using Simple Exponential Smoothing (alpha=0.3).
       This reacts to recent data without extrapolating a slope.
    2. If enough data exists (>=7 points), overlay weekday multipliers so the
       forecast reflects day-of-week patterns (e.g., weekends are higher).
    3. Confidence band = ±1 std dev of actual data, widening slightly over time.

    Returns None if fewer than 3 data points.
    Each entry: {"date": Timestamp, "value": float, "upper": float, "lower": float}
    """
    if len(values) < 3:
        return None

    date_series = pd.to_datetime(dates)
    y = np.array(values, dtype=float)

    # ── Step 1: Simple Exponential Smoothing ──────────────────────────
    # Alpha controls responsiveness: 0.3 is a balanced default that weights
    # recent observations more than old ones without being too jumpy.
    alpha = 0.3
    smoothed = y[0]
    for val in y[1:]:
        smoothed = alpha * val + (1 - alpha) * smoothed
    base_forecast = float(smoothed)

    # ── Step 2: Weekday multipliers (when enough data) ────────────────
    # Group values by weekday and compute per-weekday averages.
    # The multiplier for each weekday = (weekday avg) / (overall avg).
    # This captures patterns like "Fridays are 30% above average".
    weekday_multipliers: Dict[int, float] = {}
    overall_avg = float(np.mean(y))

    if len(values) >= 7 and overall_avg > 0:
        weekday_sums: Dict[int, float] = defaultdict(float)
        weekday_counts: Dict[int, int] = defaultdict(int)
        for dt, val in zip(date_series, y):
            wd = pd.Timestamp(dt).weekday()  # 0=Mon .. 6=Sun
            weekday_sums[wd] += val
            weekday_counts[wd] += 1
        for wd in weekday_sums:
            weekday_multipliers[wd] = (
                weekday_sums[wd] / weekday_counts[wd]
            ) / overall_avg

    # ── Step 3: Confidence band ───────────────────────────────────────
    std_dev = float(np.std(y))
    std_dev = max(std_dev, overall_avg * 0.05)  # Floor at 5% of average

    # ── Step 4: Generate forecast ─────────────────────────────────────
    if isinstance(date_series, pd.DatetimeIndex):
        last_date = pd.Timestamp(date_series[-1])
    else:
        last_date = pd.Timestamp(date_series.iloc[-1])
    forecast_dates = generate_forecast_dates(last_date, forecast_days)

    result: List[Dict[str, Any]] = []
    for i, fdate in enumerate(forecast_dates):
        value = base_forecast

        # Apply weekday adjustment if available
        wd = pd.Timestamp(fdate).weekday()
        if wd in weekday_multipliers:
            value *= weekday_multipliers[wd]

        # Band widens slightly over time to reflect growing uncertainty
        band = std_dev * (1 + i * 0.05)

        result.append(
            {
                "date": fdate,
                "value": max(0, float(value)),
                "upper": max(0, float(value + band)),
                "lower": max(0, float(value - band)),
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

    Minimum 3 data points required for forecast. With < 7 points, shows forecast
    but with wider confidence band to reflect uncertainty.
    """
    if data_points < 3:
        return 0  # Not enough data for any forecast

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
