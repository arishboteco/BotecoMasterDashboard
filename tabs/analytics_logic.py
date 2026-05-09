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
        start_date = custom_start
        end_date = custom_end
        period_key = "custom"
    else:
        period_map = {
            "7D": "last_7_days",
            "30D": "last_30_days",
            "MTD": "this_month",
            "QTD": "qtd",
            "This Week": "this_week",
            "Last Week": "last_week",
            "Last 7 Days": "last_7_days",
            "This Month": "this_month",
            "Last Month": "last_month",
            "Last 30 Days": "last_30_days",
        }
        period_key = period_map.get(
            analysis_period,
            analysis_period.lower().replace(" ", "_"),
        )

        if period_key == "qtd":
            today = date.today()
            quarter_start_month = ((today.month - 1) // 3) * 3 + 1
            start_date = date(today.year, quarter_start_month, 1)
            end_date = today
        else:
            start_date, end_date = utils.get_date_range(period_key)

    prior_start: Optional[date] = None
    prior_end: Optional[date] = None
    prior_map = {
        "this_week": None,  # same-day-span logic below
        "this_month": None,  # same-day-span logic below
        "qtd": None,  # same-day-span logic below
        "custom": None,  # same-day-span logic below
        "last_week": "last_week_prior",
        "last_month": "last_month_prior",
    }
    days_span = (end_date - start_date).days + 1
    if period_key in prior_map:
        target = prior_map[period_key]
        if target in ("last_week_prior", "last_month_prior"):
            prior_start, prior_end = utils.get_date_range(target)
        else:
            prior_end = start_date - timedelta(days=1)
            prior_start = prior_end - timedelta(days=days_span - 1)
    elif period_key in ("last_7_days", "last_30_days"):
        prior_end = start_date - timedelta(days=1)
        prior_start = prior_end - timedelta(days=days_span - 1)

    return start_date, end_date, prior_start, prior_end, period_key


def build_daily_view_table(
    df: pd.DataFrame,
    df_raw: pd.DataFrame,
    multi_analytics: bool,
    numeric: bool = False,
) -> pd.DataFrame:
    """Build and format the daily table view shown in analytics.

    If numeric=True, keeps numeric columns for conditional styling (no totals row).
    """
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
        _num_covers = pd.to_numeric(dv["covers"], errors="coerce").fillna(0)
        _num_net = pd.to_numeric(dv["net_total"], errors="coerce").fillna(0)
        _num_target = pd.to_numeric(dv["target"], errors="coerce").fillna(0)
        _num_pct = (_num_net / _num_target * 100).where(_num_target > 0, 0)
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
        _num_covers = pd.to_numeric(dv["covers"], errors="coerce").fillna(0)
        _num_net = pd.to_numeric(dv["net_total"], errors="coerce").fillna(0)
        _num_target = pd.to_numeric(dv["target"], errors="coerce").fillna(0)
        _num_pct = (_num_net / _num_target * 100).where(_num_target > 0, 0)

    if numeric:
        dv["pct_target"] = (_num_net / _num_target * 100).where(_num_target > 0, 0)
        # Add totals row
        if multi_analytics and not df_raw.empty:
            totals = pd.DataFrame(
                [
                    {
                        "date": "TOTAL",
                        "Outlet": "",
                        "covers": int(_num_covers.sum()),
                        "net_total": float(_num_net.sum()),
                        "target": float(_num_target.sum()),
                        "pct_target": float(_num_net.sum() / _num_target.sum() * 100)
                        if _num_target.sum() > 0
                        else 0,
                    }
                ]
            )
        else:
            totals = pd.DataFrame(
                [
                    {
                        "date": "TOTAL",
                        "covers": int(_num_covers.sum()),
                        "net_total": float(_num_net.sum()),
                        "target": float(_num_target.sum()),
                        "pct_target": float(_num_net.sum() / _num_target.sum() * 100)
                        if _num_target.sum() > 0
                        else 0,
                    }
                ]
            )
        dv = pd.concat([dv, totals], ignore_index=True)
        return dv

    dv["covers"] = [f"{int(x or 0):,}" for x in dv["covers"]]
    dv["net_total"] = [
        utils.format_indian_currency(float(x or 0)) for x in dv["net_total"]
    ]
    dv["target"] = [utils.format_indian_currency(float(x or 0)) for x in dv["target"]]
    dv["pct_target"] = [utils.format_percent(x) for x in _num_pct]

    # Add totals/average row
    if multi_analytics and not df_raw.empty:
        totals = pd.DataFrame(
            [
                {
                    "date": "TOTAL",
                    "Outlet": "",
                    "covers": f"{int(_num_covers.sum()):,}",
                    "net_total": utils.format_indian_currency(float(_num_net.sum())),
                    "target": utils.format_indian_currency(float(_num_target.sum())),
                    "pct_target": utils.format_percent(
                        float(_num_net.sum() / _num_target.sum() * 100)
                        if _num_target.sum() > 0
                        else 0
                    ),
                }
            ]
        )
    else:
        totals = pd.DataFrame(
            [
                {
                    "date": "TOTAL",
                    "covers": f"{int(_num_covers.sum()):,}",
                    "net_total": utils.format_indian_currency(float(_num_net.sum())),
                    "target": utils.format_indian_currency(float(_num_target.sum())),
                    "pct_target": utils.format_percent(
                        float(_num_net.sum() / _num_target.sum() * 100)
                        if _num_target.sum() > 0
                        else 0
                    ),
                }
            ]
        )
    dv = pd.concat([dv, totals], ignore_index=True)
    return dv
