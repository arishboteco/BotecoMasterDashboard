"""Analytics tab — Period selector, charts, and daily data table."""

from __future__ import annotations

from typing import Dict, List

import pandas as pd
import streamlit as st

import cache_manager
import config
import database
import scope
import utils
from tabs.analytics_logic import resolve_period_window
from tabs.analytics_sections import (
    render_overview,
    render_payment_reconciliation,
    render_revenue_breakdown,
    render_sales_performance,
    render_target_and_daily,
)
from tabs import TabContext
from components.feedback import empty_state
from components.navigation import date_range_nav
from components import page_header, page_shell, section_title

# In-process cache registered with cache_manager for coordinated invalidation
_RAW_SUMMARY_CACHE: dict = cache_manager.register("analytics_raw")


def clear_analytics_cache() -> None:
    """Clear cached analytics raw summaries."""
    cache_manager.invalidate("analytics_raw")


def _add_target_columns(
    df: pd.DataFrame,
    all_locs: list,
    location_ids: list,
) -> pd.DataFrame:
    """Add target and pct_target columns to a summaries DataFrame.

    Args:
        df: DataFrame with 'location_id', 'date', 'net_total' columns
        all_locs: List of all location dicts from database
        location_ids: List of location IDs being analyzed

    Returns:
        DataFrame with added 'target' and 'pct_target' columns
    """
    if df.empty:
        return df

    df = df.copy()

    loc_settings = {loc["id"]: loc for loc in all_locs}

    loc_monthly_target: dict = {}
    loc_weekday_mix: dict = {}
    loc_day_targets: dict = {}

    for lid in location_ids:
        settings = loc_settings.get(lid, {})
        monthly_target = float(settings.get("target_monthly_sales", 0) or 0)
        if monthly_target <= 0:
            monthly_target = float(config.MONTHLY_TARGET)
        loc_monthly_target[lid] = monthly_target

        recent = database.get_recent_summaries(lid, weeks=8)
        weekday_mix = utils.compute_weekday_mix(recent)
        loc_weekday_mix[lid] = weekday_mix

        day_targets = utils.compute_day_targets(monthly_target, weekday_mix)
        loc_day_targets[lid] = day_targets

    def _get_target_for_row(row):
        lid = row.get("location_id")
        date_str = str(row.get("date", ""))[:10]
        if lid in loc_day_targets:
            return utils.get_target_for_date(loc_day_targets[lid], date_str)
        return 0.0

    def _calc_pct_target(row):
        tgt = float(row.get("target") or 0)
        net = float(row.get("net_total") or 0)
        if tgt > 0:
            return round((net / tgt) * 100, 2)
        return 0.0

    df["target"] = df.apply(_get_target_for_row, axis=1)
    df["pct_target"] = df.apply(_calc_pct_target, axis=1)

    return df


def _load_raw_summaries_cached(
    location_ids: List[int], start_str: str, end_str: str
) -> List[Dict]:
    key = (tuple(location_ids or []), start_str, end_str)
    if key in _RAW_SUMMARY_CACHE:
        return _RAW_SUMMARY_CACHE[key]
    if not location_ids:
        raw = []
    else:
        raw = database.get_summaries_for_date_range_multi(
            location_ids, start_str, end_str
        )
    _RAW_SUMMARY_CACHE[key] = raw
    return raw


def render(ctx: TabContext) -> None:
    """Render the Analytics tab UI with charts and period analysis."""
    shell = page_shell()
    with shell.hero:
        page_header(
            title="Sales Analytics",
            subtitle=(
                "Analyze trends, category mix, target achievement, and payment reconciliation "
                "across your selected operating window."
            ),
            context="Period comparison and outlet filtering",
        )

    with shell.filters:
        section_title("Filters", "Choose period and scope for analytics.", icon="filter_alt")
        col_per1, col_per2 = st.columns([2, 3])
        with col_per1:
            default_period = "Last Month"
            if "analysis_period" not in st.session_state:
                st.session_state.analysis_period = default_period
            analysis_period = st.selectbox(
                "Time Period",
                [
                    "This Week",
                    "Last Week",
                    "Last 7 Days",
                    "This Month",
                    "Last Month",
                    "Last 30 Days",
                    "Custom",
                ],
                key="analysis_period",
            )

        custom_start = None
        custom_end = None
        if analysis_period == "Custom":
            with col_per2:
                custom_start, custom_end = date_range_nav(
                    session_key_start="analytics_custom_start",
                    session_key_end="analytics_custom_end",
                    label_start="From",
                    label_end="To",
                )
    start_date, end_date, prior_start, prior_end, _ = resolve_period_window(
        analysis_period,
        custom_start=custom_start,
        custom_end=custom_end,
    )

    with shell.filters:
        if analysis_period != "Custom":
            with col_per2:
                st.markdown(
                    f'<div class="period-range-note">'
                    f"<strong>From:</strong> {start_date.strftime('%d %b')} "
                    f"<strong>to</strong> {end_date.strftime('%d %b %Y')}"
                    f"</div>",
                    unsafe_allow_html=True,
                )

    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")

    multi_analytics = len(ctx.report_loc_ids) > 1
    analytics_loc_ids = ctx.report_loc_ids

    if multi_analytics and ctx.all_locs:
        _loc_options = ["All outlets"] + [
            loc["name"] for loc in sorted(ctx.all_locs, key=lambda x: x["name"])
        ]
        _default_idx = 0
        if "analytics_outlet_scope" not in st.session_state:
            st.session_state.analytics_outlet_scope = "All outlets"
        _current = st.session_state.get("analytics_outlet_scope", "All outlets")
        if _current in _loc_options:
            _default_idx = _loc_options.index(_current)
        with shell.filters:
            selected_outlet = st.radio(
                "Select outlet",
                options=_loc_options,
                horizontal=True,
                index=_default_idx,
                key="analytics_outlet_radio",
                label_visibility="collapsed",
            )
        st.session_state.analytics_outlet_scope = selected_outlet

        if selected_outlet != "All outlets":
            analytics_loc_ids = []
            for loc in ctx.all_locs:
                if loc["name"] == selected_outlet:
                    analytics_loc_ids = [loc["id"]]
                    break

    raw_summaries = _load_raw_summaries_cached(analytics_loc_ids, start_str, end_str)

    raw_summaries_with_targets = (
        _add_target_columns(
            pd.DataFrame(raw_summaries), ctx.all_locs, analytics_loc_ids
        ).to_dict("records")
        if raw_summaries
        else []
    )

    summaries = scope.merge_summaries_by_date(raw_summaries_with_targets)
    df_raw = pd.DataFrame(raw_summaries) if raw_summaries else pd.DataFrame()
    if multi_analytics and not df_raw.empty:
        loc_names = {loc["id"]: str(loc["name"]) for loc in ctx.all_locs}
        df_raw = df_raw.copy()
        df_raw["Outlet"] = df_raw["location_id"].map(lambda x: loc_names.get(x, str(x)))
        df_raw = _add_target_columns(df_raw, ctx.all_locs, analytics_loc_ids)

    with shell.content:
        if summaries:
            df = pd.DataFrame(summaries)

            # ── Period-over-period comparison data ───────────────────
            prior_summaries = []
            if prior_start and prior_end:
                prior_summaries = database.get_summaries_for_date_range_multi(
                    analytics_loc_ids,
                    prior_start.strftime("%Y-%m-%d"),
                    prior_end.strftime("%Y-%m-%d"),
                )
            prior_df = (
                pd.DataFrame(prior_summaries) if prior_summaries else pd.DataFrame()
            )

            total_sales = float(df["net_total"].sum())
            avg_daily = float(df["net_total"].mean())
            total_covers = int(df["covers"].sum())
            days_with_data = int(len(df[df["net_total"] > 0]))

            prior_total = (
                float(prior_df["net_total"].sum()) if not prior_df.empty else None
            )
            prior_covers = int(prior_df["covers"].sum()) if not prior_df.empty else None
            prior_avg = float(prior_df["net_total"].mean()) if not prior_df.empty else None

            render_overview(
                analysis_period,
                start_date,
                total_sales,
                avg_daily,
                total_covers,
                days_with_data,
                prior_total,
                prior_covers,
                prior_avg,
            )
            render_sales_performance(
                df,
                df_raw,
                multi_analytics,
                prior_df=prior_df,
                analysis_period=analysis_period,
            )
            render_revenue_breakdown(
                analytics_loc_ids,
                start_str,
                end_str,
                df,
                start_date,
            )
            render_target_and_daily(
                analytics_loc_ids,
                start_date,
                df,
                df_raw,
                multi_analytics,
                analysis_period=analysis_period,
            )
            render_payment_reconciliation(analytics_loc_ids, start_str, end_str)

        else:
            empty_state(
                message="No data available",
                hint=(
                    "This period has no sales data yet. "
                    "Upload POS files from the <strong>Upload</strong> tab or select a different time range."
                    "<br><br>"
                    "<strong>Tip:</strong> Try selecting &lsquo;Last Month&rsquo; or &lsquo;Last 30 Days&rsquo; to see recent data."
                ),
                icon="insights",
            )
