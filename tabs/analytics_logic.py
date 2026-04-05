"""Pure helper logic for analytics tab period/date and table formatting."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Optional, Tuple

import pandas as pd

import utils


def resolve_period_window(
    analysis_period: str,
    custom_start: Optional[date] = None,
    custom_end: Optional[date] = None,
) -> Tuple[date, date, Optional[date], Optional[date], Optional[str]]:
    """Return (start, end, prior_start, prior_end, period_key)."""
    if analysis_period == "Custom":
        if custom_start is None or custom_end is None:
            raise ValueError("Custom period requires start and end dates")
        return custom_start, custom_end, None, None, None

    period_key = analysis_period.lower().replace(" ", "_")
    start_date, end_date = utils.get_date_range(period_key)

    prior_start: Optional[date] = None
    prior_end: Optional[date] = None
    prior_map = {
        "this_week": "last_week",
        "this_month": "last_month",
    }
    days_span = (end_date - start_date).days + 1
    if period_key in prior_map:
        prior_start, prior_end = utils.get_date_range(prior_map[period_key])
    elif period_key in ("last_7_days", "last_30_days"):
        prior_end = start_date - timedelta(days=1)
        prior_start = prior_end - timedelta(days=days_span - 1)

    return start_date, end_date, prior_start, prior_end, period_key


def build_daily_view_table(
    df: pd.DataFrame,
    df_raw: pd.DataFrame,
    multi_analytics: bool,
) -> pd.DataFrame:
    """Build and format the daily table view shown in analytics."""
    if multi_analytics and not df_raw.empty:
        dv = (
            df_raw[
                [
                    "date",
                    "Outlet",
                    "covers",
                    "net_total",
                    "target",
                    "pct_target",
                ]
            ]
            .sort_values(["date", "Outlet"])
            .copy()
        )
    elif multi_analytics:
        return pd.DataFrame()
    else:
        dv = (
            df[
                [
                    "date",
                    "covers",
                    "net_total",
                    "target",
                    "pct_target",
                ]
            ]
            .sort_values("date")
            .copy()
        )

    dv["covers"] = [f"{int(x or 0):,}" for x in dv["covers"]]
    dv["net_total"] = [utils.format_currency(float(x or 0)) for x in dv["net_total"]]
    dv["target"] = [utils.format_currency(float(x or 0)) for x in dv["target"]]
    dv["pct_target"] = [utils.format_percent(float(x or 0)) for x in dv["pct_target"]]
    return dv
