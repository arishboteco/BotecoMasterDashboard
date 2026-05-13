"""Forecasting helpers for analytics charts.

Pure functions: restaurant-focused sales forecast, moving average, forecast date generation.
No Streamlit or database dependencies.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd


def _bounded(value: float, lower: float, upper: float) -> float:
    """Clamp a numeric value between lower and upper bounds."""
    return max(lower, min(upper, float(value)))


def _prepare_daily_series(
    dates: pd.Series,
    values: List[float],
) -> pd.DataFrame:
    """Clean, sort and aggregate input dates/values to one row per day."""
    raw_df = pd.DataFrame(
        {
            "date": pd.to_datetime(pd.Series(dates), errors="coerce"),
            "value": pd.to_numeric(pd.Series(values), errors="coerce"),
        }
    )

    raw_df = raw_df.dropna(subset=["date", "value"]).copy()

    if raw_df.empty:
        return pd.DataFrame(columns=["date", "value", "weekday"])

    raw_df["date"] = raw_df["date"].dt.normalize()
    raw_df["value"] = raw_df["value"].clip(lower=0)

    daily_df = (
        raw_df.groupby("date", as_index=False)["value"]
        .sum()
        .sort_values("date")
        .reset_index(drop=True)
    )

    daily_df["weekday"] = daily_df["date"].dt.weekday

    return daily_df


def _simple_exponential_smoothing(values: np.ndarray, alpha: float) -> float:
    """Calculate a simple exponential smoothing terminal value."""
    smoothed = float(values[0])

    for value in values[1:]:
        smoothed = alpha * float(value) + (1 - alpha) * smoothed

    return float(smoothed)


def _build_weekday_multipliers(
    daily_df: pd.DataFrame,
    overall_avg: float,
) -> tuple[dict[int, float], int]:
    """Build conservative weekday multipliers from historical same-weekday performance."""
    if daily_df.empty or overall_avg <= 0:
        return {}, 0

    weekday_multipliers: dict[int, float] = {}

    for weekday, weekday_df in daily_df.groupby("weekday"):
        if len(weekday_df) < 2:
            continue

        weekday_median = float(weekday_df["value"].median())
        raw_multiplier = weekday_median / overall_avg if overall_avg > 0 else 1.0

        # Shrink the multiplier toward 1.0 so one unusual weekday does not dominate.
        conservative_multiplier = 1 + ((raw_multiplier - 1) * 0.65)

        # Cap extreme weekday effects.
        weekday_multipliers[int(weekday)] = _bounded(
            conservative_multiplier,
            0.65,
            1.45,
        )

    return weekday_multipliers, len(weekday_multipliers)


def _forecast_reliability(
    data_points: int,
    volatility_pct: float,
    weekday_coverage: int,
) -> tuple[str, list[str]]:
    """Return forecast reliability label and explanation reasons."""
    score = 0
    reasons: list[str] = []

    if data_points >= 28:
        score += 2
        reasons.append("28+ days of history available.")
    elif data_points >= 14:
        score += 1
        reasons.append("14+ days of history available.")
    elif data_points >= 7:
        reasons.append("Only 7–13 days of history available.")
    else:
        reasons.append("Fewer than 7 days of history available.")

    if volatility_pct <= 0.15:
        score += 2
        reasons.append("Sales volatility is low.")
    elif volatility_pct <= 0.30:
        score += 1
        reasons.append("Sales volatility is moderate.")
    else:
        reasons.append("Sales volatility is high.")

    if weekday_coverage >= 5:
        score += 1
        reasons.append("Enough weekday pattern coverage is available.")
    elif weekday_coverage > 0:
        reasons.append("Partial weekday pattern coverage is available.")
    else:
        reasons.append("Weekday pattern coverage is limited.")

    if score >= 4:
        return "High", reasons

    if score >= 2:
        return "Medium", reasons

    return "Low", reasons


def linear_forecast(
    dates: pd.Series,
    values: List[float],
    forecast_days: int = 5,
) -> Optional[List[Dict[str, Any]]]:
    """Forecast future restaurant sales using weighted smoothing + weekday pattern logic.

    This is not a machine-learning model. It is a transparent statistical forecast.

    Approach:
    1. Clean the daily series and aggregate duplicate dates.
    2. Use simple exponential smoothing for a stable baseline.
    3. Blend the baseline with recent 7-day and 14-day averages.
    4. Apply conservative weekday multipliers only when same-weekday history is sufficient.
    5. Apply a capped recent-trend adjustment.
    6. Build volatility-aware confidence bands.

    Returns None if fewer than 3 valid daily data points are available.
    Each entry includes:
    {
        "date": Timestamp,
        "value": float,
        "upper": float,
        "lower": float,
        "metadata": dict
    }
    """
    if forecast_days <= 0:
        return None

    daily_df = _prepare_daily_series(dates, values)

    if len(daily_df) < 3:
        return None

    y = daily_df["value"].to_numpy(dtype=float)
    data_points = len(y)

    overall_avg = float(np.mean(y)) if data_points > 0 else 0.0
    recent_7_avg = float(np.mean(y[-min(7, data_points):]))
    recent_14_avg = float(np.mean(y[-min(14, data_points):]))

    if data_points >= 21:
        alpha = 0.25
    elif data_points >= 10:
        alpha = 0.30
    else:
        alpha = 0.40

    smoothed = _simple_exponential_smoothing(y, alpha=alpha)

    if data_points >= 14:
        base_forecast = (
            (0.45 * smoothed)
            + (0.35 * recent_7_avg)
            + (0.20 * recent_14_avg)
        )
    elif data_points >= 7:
        base_forecast = (0.55 * smoothed) + (0.45 * recent_7_avg)
    else:
        base_forecast = smoothed

    # Recent trend: compare latest 7 days against the previous 7 days when available.
    trend_pct = 0.0
    if data_points >= 14:
        previous_7_avg = float(np.mean(y[-14:-7]))
        if previous_7_avg > 0:
            trend_pct = (recent_7_avg / previous_7_avg) - 1.0

    # Do not allow recent trend to swing the forecast too aggressively.
    safe_trend_pct = _bounded(trend_pct, -0.20, 0.20)

    weekday_multipliers, weekday_coverage = _build_weekday_multipliers(
        daily_df,
        overall_avg,
    )

    std_dev = float(np.std(y))
    volatility_pct = std_dev / overall_avg if overall_avg > 0 else 0.35
    volatility_pct = _bounded(volatility_pct, 0.08, 0.45)

    reliability_label, reliability_reasons = _forecast_reliability(
        data_points=data_points,
        volatility_pct=volatility_pct,
        weekday_coverage=weekday_coverage,
    )

    last_date = pd.Timestamp(daily_df["date"].iloc[-1])
    forecast_dates = generate_forecast_dates(last_date, forecast_days)

    result: List[Dict[str, Any]] = []

    for index, forecast_date in enumerate(forecast_dates):
        weekday = pd.Timestamp(forecast_date).weekday()

        weekday_multiplier = weekday_multipliers.get(weekday, 1.0)

        # Spread the recent trend effect gradually across forecast days.
        trend_multiplier = 1 + (safe_trend_pct * min((index + 1) / 7, 1) * 0.50)

        forecast_value = base_forecast * weekday_multiplier * trend_multiplier
        forecast_value = max(0, float(forecast_value))

        band = forecast_value * volatility_pct * (1 + index * 0.06)

        metadata = {
            "model_label": "Weighted smoothing + weekday adjustment",
            "alpha": alpha,
            "data_points": data_points,
            "overall_avg": overall_avg,
            "recent_7_avg": recent_7_avg,
            "recent_14_avg": recent_14_avg,
            "base_forecast": base_forecast,
            "trend_pct": trend_pct,
            "safe_trend_pct": safe_trend_pct,
            "weekday_multiplier": weekday_multiplier,
            "weekday_adjustment_applied": weekday_multiplier != 1.0,
            "weekday_coverage": weekday_coverage,
            "volatility_pct": volatility_pct,
            "reliability": reliability_label,
            "reliability_reasons": reliability_reasons,
        }

        result.append(
            {
                "date": forecast_date,
                "value": forecast_value,
                "upper": max(0, float(forecast_value + band)),
                "lower": max(0, float(forecast_value - band)),
                "metadata": metadata,
            }
        )

    return result


def build_forecast_explanation(
    values: List[float],
    forecast: Optional[List[Dict[str, Any]]],
) -> dict[str, Any]:
    """Build a UI-ready explanation for the forecast output."""
    if not forecast:
        return {
            "available": False,
            "reason": "Forecast is unavailable because there are not enough valid data points or the selected period is closed.",
        }

    metadata = forecast[0].get("metadata", {})

    forecast_values = [float(item.get("value", 0) or 0) for item in forecast]
    total_forecast = float(sum(forecast_values))
    avg_forecast = float(np.mean(forecast_values)) if forecast_values else 0.0

    trend_pct = float(metadata.get("trend_pct", 0) or 0)
    safe_trend_pct = float(metadata.get("safe_trend_pct", 0) or 0)
    volatility_pct = float(metadata.get("volatility_pct", 0) or 0)

    drivers: list[str] = []

    drivers.append(
        "Forecast uses a weighted blend of exponential smoothing, recent 7-day average and recent 14-day average."
    )

    if metadata.get("weekday_coverage", 0) >= 5:
        drivers.append(
            "Weekday adjustment is active because sufficient same-weekday history is available."
        )
    elif metadata.get("weekday_coverage", 0) > 0:
        drivers.append(
            "Weekday adjustment is partially active because only some weekdays have enough history."
        )
    else:
        drivers.append(
            "Weekday adjustment is limited because same-weekday history is insufficient."
        )

    if abs(trend_pct) >= 0.05:
        drivers.append(
            f"Recent 7-day trend is {trend_pct * 100:+.1f}%; model applies a capped trend of {safe_trend_pct * 100:+.1f}%."
        )
    else:
        drivers.append(
            "Recent 7-day trend is broadly stable, so the model applies minimal trend pressure."
        )

    cautions: list[str] = []

    if metadata.get("reliability") == "Low":
        cautions.append(
            "Low forecast confidence: use this as a directional estimate, not a firm prediction."
        )

    if volatility_pct >= 0.30:
        cautions.append(
            "High sales volatility detected; actual sales may move materially outside the central forecast."
        )

    if metadata.get("data_points", 0) < 14:
        cautions.append(
            "Less than 14 days of data is available, so weekday and trend patterns may be weak."
        )

    return {
        "available": True,
        "model_label": metadata.get("model_label", "Weighted smoothing forecast"),
        "confidence": metadata.get("reliability", "Low"),
        "data_points": int(metadata.get("data_points", 0) or 0),
        "forecast_days": len(forecast),
        "total_forecast": total_forecast,
        "avg_forecast": avg_forecast,
        "overall_avg": float(metadata.get("overall_avg", 0) or 0),
        "recent_7_avg": float(metadata.get("recent_7_avg", 0) or 0),
        "recent_14_avg": float(metadata.get("recent_14_avg", 0) or 0),
        "base_forecast": float(metadata.get("base_forecast", 0) or 0),
        "trend_pct": trend_pct,
        "safe_trend_pct": safe_trend_pct,
        "volatility_pct": volatility_pct,
        "weekday_coverage": int(metadata.get("weekday_coverage", 0) or 0),
        "drivers": drivers,
        "cautions": cautions,
        "reliability_reasons": metadata.get("reliability_reasons", []),
    }


def moving_average(
    values: List[float],
    window: int = 7,
) -> List[float]:
    """Compute simple moving average. Returns same length as input.

    Leading entries before enough data for the window are NaN.
    """
    if window <= 0:
        return list(values)

    if window == 1:
        return list(values)

    result: List[float] = []

    for index in range(len(values)):
        if index < window - 1:
            result.append(float("nan"))
        else:
            window_vals = values[index - window + 1 : index + 1]
            result.append(sum(window_vals) / len(window_vals))

    return result


def generate_forecast_dates(
    last_date: pd.Timestamp,
    forecast_days: int,
) -> List[pd.Timestamp]:
    """Generate consecutive dates starting the day after last_date."""
    return [last_date + timedelta(days=index + 1) for index in range(forecast_days)]


def calculate_forecast_days(
    analysis_period: str,
    data_points: int = 0,
    selected_range_days: int = 0,
) -> int:
    """Calculate forecast length based on selected analysis period.

    Rules:
    - Closed historical periods such as LM / Last Month should not forecast forward.
    - Rolling 7D / 30D / Custom ranges get a short forward-looking forecast.
    - MTD forecasts to month-end.
    - QTD forecasts to quarter-end.
    - YTD is capped to 30 days because full-year forecasting from daily sales is too uncertain.
    """
    if data_points < 3:
        return 0

    period_key = analysis_period.lower().replace(" ", "_")

    # Closed historical periods should show actuals only, not a future forecast.
    if period_key in {"lm", "last_month", "last_week"}:
        return 0

    if period_key in {"7d", "last_7_days"}:
        return 3

    if period_key in {"30d", "last_30_days", "custom"}:
        if selected_range_days > 0:
            return max(1, min(7, selected_range_days // 2))
        return 7

    if period_key in {"this_month", "mtd"}:
        today = date.today()

        if today.month == 12:
            next_month = date(today.year + 1, 1, 1)
        else:
            next_month = date(today.year, today.month + 1, 1)

        return max(1, (next_month - today).days)

    if period_key in {"qtd"}:
        today = date.today()
        quarter_start_month = ((today.month - 1) // 3) * 3 + 1
        quarter_end_month = quarter_start_month + 2

        if quarter_end_month == 12:
            next_quarter = date(today.year + 1, 1, 1)
        else:
            next_quarter = date(today.year, quarter_end_month + 1, 1)

        return max(1, (next_quarter - today).days)

    if period_key in {"ytd"}:
        today = date.today()
        year_end = date(today.year + 1, 1, 1)
        return max(1, min(30, (year_end - today).days))

    return 7