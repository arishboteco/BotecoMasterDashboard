"""Forecasting helpers for analytics charts.

Pure functions: restaurant-focused sales forecast, moving average, forecast date generation.
No Streamlit or database dependencies.
"""

from __future__ import annotations

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
    # Drop any incoming index before pairing. A filtered Series keeps the index
    # it was sliced from, and pandas would align it against a plain list's 0..n
    # index — silently pairing each date with another day's value.
    date_series = pd.Series(dates).reset_index(drop=True)
    value_series = pd.Series(values).reset_index(drop=True)

    raw_df = pd.DataFrame(
        {
            "date": pd.to_datetime(date_series, errors="coerce"),
            "value": pd.to_numeric(value_series, errors="coerce"),
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


# A weekday seen this many times is treated as fully measured; below that its
# effect is scaled back toward the overall average in proportion to the evidence.
WEEKDAY_MIN_OBSERVATIONS = 4

# Outer bounds on a single weekday's effect. Deliberately wide: real restaurant
# weekday spreads exceed 3x, and clipping a genuine pattern biases the forecast.
WEEKDAY_FACTOR_FLOOR = 0.30
WEEKDAY_FACTOR_CEILING = 2.00


def _trading_days(daily_df: pd.DataFrame) -> pd.DataFrame:
    """Rows where the outlet actually traded.

    Closed days are real zeros, not typical days, so averaging them in would drag
    every forecast down. They are excluded from fitting but stay in the actuals.
    """
    if daily_df.empty:
        return daily_df

    return daily_df[daily_df["value"] > 0].reset_index(drop=True)


def build_weekday_shape(
    dates: pd.Series,
    values: List[float],
) -> dict[int, float]:
    """Return the weekday factors the forecast would apply to this history.

    Exposed so target plans can be shaped by the same weekday pattern the
    forecast uses, instead of spreading a target flat across very unequal days.
    Weekdays without any history are simply absent (callers treat them as 1.0).

    Returns an empty mapping until a full week has traded. Shaping a whole
    month's target from a part-week would spread it by which days happen to have
    opened rather than by any real pattern; callers fall back to an even spread.
    """
    trading = _trading_days(_prepare_daily_series(dates, values))

    if len(trading) < 7:
        return {}

    factors, _coverage = _build_weekday_multipliers(
        trading,
        float(trading["value"].mean()),
    )

    return factors


def _build_weekday_multipliers(
    daily_df: pd.DataFrame,
    overall_avg: float,
) -> tuple[dict[int, float], int]:
    """Measure how each weekday performs relative to an average trading day.

    Each weekday's factor is simply its own mean divided by the overall mean, so
    a Saturday that really earns 1.5x an average day is forecast at 1.5x. The
    only adjustment is for thin evidence: a weekday seen fewer than
    ``WEEKDAY_MIN_OBSERVATIONS`` times has its effect scaled back proportionally,
    which matters for a newly opened outlet and fades away as history builds.

    Backtesting on this dataset showed that shrinking well-evidenced weekday
    effects toward flat — the previous behaviour — cost more accuracy than the
    occasional odd weekday it guarded against.
    """
    if daily_df.empty or overall_avg <= 0:
        return {}, 0

    weekday_multipliers: dict[int, float] = {}
    well_evidenced = 0

    for weekday, weekday_df in daily_df.groupby("weekday"):
        observations = len(weekday_df)

        if observations < 1:
            continue

        weekday_mean = float(weekday_df["value"].mean())
        raw_multiplier = weekday_mean / overall_avg

        evidence = min(1.0, observations / WEEKDAY_MIN_OBSERVATIONS)
        adjusted = 1 + ((raw_multiplier - 1) * evidence)

        weekday_multipliers[int(weekday)] = _bounded(
            adjusted,
            WEEKDAY_FACTOR_FLOOR,
            WEEKDAY_FACTOR_CEILING,
        )

        if observations >= WEEKDAY_MIN_OBSERVATIONS:
            well_evidenced += 1

    return weekday_multipliers, well_evidenced


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
    forecast_after_date: date | pd.Timestamp | None = None,
) -> Optional[List[Dict[str, Any]]]:
    """Forecast future restaurant sales from same-weekday averages.

    This is not a machine-learning model. It is a transparent statistical forecast,
    and a deliberately simple one: backtesting on this dataset found that a plain
    per-weekday average beat exponential smoothing, trend terms and shrunk weekday
    multipliers, because a restaurant week is a strong, stable, repeating pattern
    and the extra machinery mostly damped that real signal.

    Approach:
    1. Clean the daily series and aggregate duplicate dates.
    2. Drop closed days, which are zeros rather than typical trading days.
    3. Take the average trading day as the baseline level.
    4. Scale it by how that weekday actually performs, easing the effect in only
       while a weekday still has thin history.
    5. Build confidence bands from how far this model has actually missed on the
       history it was fitted to, rather than from raw dispersion.

    Returns None if fewer than 3 trading days are available. Each entry includes:
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
    trading_df = _trading_days(daily_df)

    if len(trading_df) < 3:
        return None

    y = trading_df["value"].to_numpy(dtype=float)
    data_points = len(y)

    overall_avg = float(np.mean(y))

    if overall_avg <= 0:
        return None

    recent_7_avg = float(np.mean(y[-min(7, data_points):]))
    recent_14_avg = float(np.mean(y[-min(14, data_points):]))

    weekday_multipliers, weekday_coverage = _build_weekday_multipliers(
        trading_df,
        overall_avg,
    )

    # Confidence bands come from this model's own historical error: fit each past
    # trading day and measure the spread of what it got wrong. That is a truer
    # statement of uncertainty than the spread of the raw numbers, most of which
    # is the weekday pattern the model already explains.
    fitted = overall_avg * np.array(
        [weekday_multipliers.get(int(wd), 1.0) for wd in trading_df["weekday"]],
        dtype=float,
    )
    residual_std = float(np.std(y - fitted))
    volatility_pct = _bounded(residual_std / overall_avg, 0.08, 0.45)

    # Reported for context only; the forecast itself applies no trend term.
    trend_pct = 0.0
    if data_points >= 14:
        previous_7_avg = float(np.mean(y[-14:-7]))
        if previous_7_avg > 0:
            trend_pct = (recent_7_avg / previous_7_avg) - 1.0

    reliability_label, reliability_reasons = _forecast_reliability(
        data_points=data_points,
        volatility_pct=volatility_pct,
        weekday_coverage=weekday_coverage,
    )

    last_date = (
        pd.Timestamp(forecast_after_date).normalize()
        if forecast_after_date is not None
        else pd.Timestamp(daily_df["date"].iloc[-1])
    )
    forecast_dates = generate_forecast_dates(last_date, forecast_days)

    result: List[Dict[str, Any]] = []

    for index, forecast_date in enumerate(forecast_dates):
        weekday = pd.Timestamp(forecast_date).weekday()

        weekday_multiplier = weekday_multipliers.get(weekday, 1.0)

        forecast_value = max(0, float(overall_avg * weekday_multiplier))

        band = forecast_value * volatility_pct * (1 + index * 0.06)

        metadata = {
            "model_label": "Same-weekday average",
            "data_points": data_points,
            "overall_avg": overall_avg,
            "recent_7_avg": recent_7_avg,
            "recent_14_avg": recent_14_avg,
            "base_forecast": overall_avg,
            "trend_pct": trend_pct,
            "safe_trend_pct": 0.0,
            "weekday_multiplier": weekday_multiplier,
            "weekday_adjustment_applied": weekday_multiplier != 1.0,
            "weekday_coverage": weekday_coverage,
            "weekday_multipliers": dict(weekday_multipliers),
            "volatility_pct": volatility_pct,
            "residual_std": residual_std,
            "closed_days_excluded": int(len(daily_df) - data_points),
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

    overall_avg = float(metadata.get("overall_avg", 0) or 0)
    multipliers = metadata.get("weekday_multipliers") or {}

    drivers: list[str] = []

    drivers.append(
        f"Each day is forecast as the average trading day "
        f"({overall_avg:,.0f}) scaled by how that weekday actually performs."
    )

    if multipliers:
        names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        strongest = max(multipliers, key=multipliers.get)
        weakest = min(multipliers, key=multipliers.get)
        drivers.append(
            f"Strongest day is {names[int(strongest)]} at "
            f"{multipliers[strongest]:.2f}x an average day; weakest is "
            f"{names[int(weakest)]} at {multipliers[weakest]:.2f}x."
        )

    if metadata.get("weekday_coverage", 0) >= 5:
        drivers.append(
            "Every weekday has enough history for its own average to be used directly."
        )
    elif metadata.get("weekday_coverage", 0) > 0:
        drivers.append(
            "Some weekdays still have thin history, so their effect is eased in gradually."
        )
    else:
        drivers.append(
            "Weekday history is thin, so days are forecast close to the overall average."
        )

    if abs(trend_pct) >= 0.05:
        drivers.append(
            f"For context, the last 7 days ran {trend_pct * 100:+.1f}% against the 7 before; "
            "the forecast applies no trend term, so a sustained shift shows up as the "
            "averages move."
        )

    closed_days = int(metadata.get("closed_days_excluded", 0) or 0)
    if closed_days:
        drivers.append(
            f"{closed_days} closed day(s) were excluded from the averages."
        )

    cautions: list[str] = []

    if metadata.get("reliability") == "Low":
        cautions.append(
            "Low forecast confidence: use this as a directional estimate, not a firm prediction."
        )

    if volatility_pct >= 0.30:
        cautions.append(
            "Day-to-day sales vary widely even after allowing for the weekday pattern; "
            "actual sales may move materially outside the central forecast."
        )

    if metadata.get("data_points", 0) < 14:
        cautions.append(
            "Less than 14 trading days are available, so the weekday pattern may be weak."
        )

    return {
        "available": True,
        "model_label": metadata.get("model_label", "Same-weekday average"),
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

    Open/current periods should forecast forward.
    Closed historical periods should not forecast forward; they should use backtesting instead.
    """
    if data_points < 3:
        return 0

    period_key = analysis_period.lower().replace(" ", "_")

    # Closed historical periods: no forward forecast.
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
