"""Analytics tab — Period selector, charts, and daily data table."""

from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd
import streamlit as st

import database
import scope
from tabs.analytics_logic import resolve_period_window
from tabs.analytics_sections import (
    render_overview,
    render_revenue_breakdown,
    render_sales_performance,
    render_target_and_daily,
)
from tabs import TabContext


def render(ctx: TabContext) -> None:
    """Render the Analytics tab UI with charts and period analysis."""
    st.header("Sales Analytics")
    st.caption(f"Viewing: **{ctx.report_display_name}** — trends for the period below.")
    st.divider()

    # ── Period selector ──────────────────────────────────────────
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
            c1, c2 = st.columns(2)
            with c1:
                custom_start = st.date_input(
                    "From",
                    datetime.now().date() - timedelta(days=29),
                    key="analytics_custom_start",
                )
            with c2:
                custom_end = st.date_input(
                    "To",
                    datetime.now().date(),
                    key="analytics_custom_end",
                )
    start_date, end_date, prior_start, prior_end, _ = resolve_period_window(
        analysis_period,
        custom_start=custom_start,
        custom_end=custom_end,
    )

    if analysis_period != "Custom":
        with col_per2:
            st.markdown(
                f'<div style="padding:0.5rem 0;font-size:0.95rem;color:var(--text-secondary);">'
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

    raw_summaries = database.get_summaries_for_date_range_multi(
        analytics_loc_ids,
        start_str,
        end_str,
    )
    summaries = scope.merge_summaries_by_date(raw_summaries)
    df_raw = pd.DataFrame(raw_summaries) if raw_summaries else pd.DataFrame()
    if multi_analytics and not df_raw.empty:
        loc_names = {loc["id"]: str(loc["name"]) for loc in ctx.all_locs}
        df_raw = df_raw.copy()
        df_raw["Outlet"] = df_raw["location_id"].map(lambda x: loc_names.get(x, str(x)))

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
        prior_df = pd.DataFrame(prior_summaries) if prior_summaries else pd.DataFrame()

        total_sales = float(df["net_total"].sum())
        avg_daily = float(df["net_total"].mean())
        total_covers = int(df["covers"].sum())
        days_with_data = int(len(df[df["net_total"] > 0]))

        prior_total = float(prior_df["net_total"].sum()) if not prior_df.empty else None
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

    else:
        st.markdown(
            '<div class="empty-state">'
            '<div class="empty-state-icon material-symbols-outlined">insights</div>'
            '<div class="empty-state-title">No data available</div>'
            '<div class="empty-state-desc">'
            "This period has no sales data yet. "
            "Upload POS files from the **Upload** tab or select a different time range."
            "<br><br>"
            "<strong>Tip:</strong> Try selecting 'Last Month' or 'Last 30 Days' to see recent data."
            "</div>"
            "</div>",
            unsafe_allow_html=True,
        )
