"""Analytics tab — Period selector, charts, and daily data table."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

import config
import database
import scope
import ui_theme
import utils
from tabs import TabContext
from components import kpi_row, KpiMetric, data_table


def render(ctx: TabContext) -> None:
    """Render the Analytics tab UI with charts and period analysis."""
    st.header("Sales Analytics")
    st.caption(f"Viewing: **{ctx.report_display_name}** — trends for the period below.")
    st.divider()

    # ── Period selector ──────────────────────────────────────────
    col_per1, col_per2 = st.columns([2, 3])
    with col_per1:
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
        start_date, end_date = custom_start, custom_end
        prior_start, prior_end = None, None
    else:
        period_key = analysis_period.lower().replace(" ", "_")
        start_date, end_date = utils.get_date_range(period_key)

        # Determine comparison period for period-over-period deltas
        _prior_map = {
            "this_week": "last_week",
            "this_month": "last_month",
        }
        _days_span = (end_date - start_date).days + 1
        if period_key in _prior_map:
            prior_start, prior_end = utils.get_date_range(_prior_map[period_key])
        elif period_key in ("last_7_days", "last_30_days"):
            prior_end = start_date - timedelta(days=1)
            prior_start = prior_end - timedelta(days=_days_span - 1)
        else:
            prior_start, prior_end = None, None

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

    raw_summaries = database.get_summaries_for_date_range_multi(
        ctx.report_loc_ids,
        start_str,
        end_str,
    )
    summaries = scope.merge_summaries_by_date(raw_summaries)
    multi_analytics = len(ctx.report_loc_ids) > 1
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
                ctx.report_loc_ids,
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

        # ── Section 1: Overview ───────────────────────────────────
        with st.expander("📊 Overview", expanded=True):
            st.markdown("### Period Summary")
            with st.container(border=True):
                # How many columns: 4 base + 1 projection when "This Month"
                show_projection = analysis_period == "This Month"
                _ncols = 5 if show_projection else 4
                kpi_cols = st.columns(_ncols)

                def _delta_str(current, prior):
                    if prior is None or prior == 0:
                        return None
                    g = utils.calculate_growth(current, prior)
                    return utils.format_delta(current, prior)

                with kpi_cols[0]:
                    st.metric(
                        "Total Sales",
                        utils.format_currency(total_sales),
                        delta=_delta_str(total_sales, prior_total),
                    )
                with kpi_cols[1]:
                    cov_delta = None
                    if prior_covers is not None and prior_covers > 0:
                        g = utils.calculate_growth(total_covers, prior_covers)
                        sign = "+" if g["change"] >= 0 else ""
                        cov_delta = f"{sign}{int(g['change']):,} ({sign}{utils.format_percent(g['percentage'])})"
                    st.metric(
                        "Total Covers",
                        f"{total_covers:,}",
                        delta=cov_delta,
                    )
                with kpi_cols[2]:
                    st.metric(
                        "Avg Daily Sales",
                        utils.format_currency(avg_daily),
                        delta=_delta_str(avg_daily, prior_avg),
                    )
                with kpi_cols[3]:
                    st.metric("Days with Data", days_with_data)

                if show_projection:
                    days_in_mo = utils.get_days_in_month(
                        start_date.year, start_date.month
                    )
                    projected = utils.calculate_projected_sales(
                        total_sales, days_with_data, days_in_mo
                    )
                    with kpi_cols[4]:
                        st.metric(
                            "Projected Month-End",
                            utils.format_currency(projected),
                            help="Based on current run rate extrapolated to end of month.",
                        )

        # ── Section 2: Sales Performance ─────────────────────────
        with st.expander("💰 Sales Performance", expanded=True):
            col_chart1, col_chart2 = st.columns(2)

            with col_chart1:
                st.markdown("### Daily Sales Trend")
                if multi_analytics and not df_raw.empty:
                    fig_line = px.line(
                        df_raw,
                        x="date",
                        y="net_total",
                        color="Outlet",
                        markers=True,
                        title="Net sales by outlet",
                    )
                else:
                    fig_line = px.line(
                        df,
                        x="date",
                        y="net_total",
                        markers=True,
                        title="Net Sales Over Time",
                    )
                    fig_line.update_traces(line_color=ui_theme.BRAND_PRIMARY)
                fig_line.update_layout(
                    xaxis_title="Date",
                    yaxis_title="Net Sales (₹)",
                    hovermode="x unified",
                    height=ui_theme.CHART_HEIGHT,
                )
                st.plotly_chart(fig_line, use_container_width=True)

            with col_chart2:
                st.markdown("### Covers Trend")
                if multi_analytics and not df_raw.empty:
                    fig_bar = px.bar(
                        df_raw,
                        x="date",
                        y="covers",
                        color="Outlet",
                        barmode="group",
                        title="Daily covers by outlet",
                    )
                else:
                    fig_bar = px.bar(df, x="date", y="covers", title="Daily Covers")
                    fig_bar.update_traces(marker_color=ui_theme.BRAND_SUCCESS)
                fig_bar.update_layout(
                    xaxis_title="Date",
                    yaxis_title="Covers",
                    height=ui_theme.CHART_HEIGHT,
                )
                st.plotly_chart(fig_bar, use_container_width=True)

            # ── APC Trend ────────────────────────────────────────────
            st.markdown("### Average Per Cover (APC) Trend")
            apc_df = df[df["apc"] > 0].copy() if "apc" in df.columns else pd.DataFrame()
            if not apc_df.empty:
                fig_apc = px.line(
                    apc_df,
                    x="date",
                    y="apc",
                    markers=True,
                    title="APC over time",
                )
                fig_apc.update_traces(line_color=ui_theme.BRAND_PRIMARY)
                avg_apc = float(apc_df["apc"].mean())
                fig_apc.add_hline(
                    y=avg_apc,
                    line_dash="dash",
                    line_color="gray",
                    annotation_text=f"Avg {utils.format_currency(avg_apc)}",
                    annotation_position="top right",
                )
                fig_apc.update_layout(
                    xaxis_title="Date",
                    yaxis_title="APC (₹)",
                    hovermode="x unified",
                    height=ui_theme.CHART_HEIGHT,
                )
                st.plotly_chart(fig_apc, use_container_width=True)
            else:
                st.caption("No APC data for this period.")

        # ── Section 3: Revenue Breakdown ───────────────────────────
        with st.expander("📈 Revenue Breakdown", expanded=True):
            st.markdown("### Payment Mode Distribution")
            payment_totals = {
                "Cash": float(df["cash_sales"].sum()),
                "GPay": float(df["gpay_sales"].sum()),
                "Zomato": float(df["zomato_sales"].sum()),
                "Card": float(df["card_sales"].sum()),
                "Other": float(df["other_sales"].sum()),
            }
            pay_df = pd.DataFrame(
                {
                    "Mode": list(payment_totals.keys()),
                    "Amount": list(payment_totals.values()),
                }
            ).sort_values("Amount", ascending=True)
            fig_pay = px.bar(
                pay_df,
                x="Amount",
                y="Mode",
                orientation="h",
                title="Payment mode split (₹)",
                color="Mode",
                color_discrete_map={
                    "Cash": ui_theme.BRAND_PRIMARY,  # #1F5FA8 — deep royal blue
                    "GPay": ui_theme.BRAND_SECONDARY,  # #3FA7A3 — teal blue
                    "Zomato": ui_theme.BRAND_GREEN,  # #6DBE45 — leaf green
                    "Card": ui_theme.BRAND_WARN,  # #F4B400 — golden mustard
                    "Other": ui_theme.BRAND_DARK,  # #174A82 — dark blue
                },
            )
        fig_pay.update_layout(
            xaxis_title="Amount (₹)",
            yaxis_title="",
            height=ui_theme.CHART_HEIGHT,
            showlegend=False,
        )
        st.plotly_chart(fig_pay, use_container_width=True)

        # ── Category Sales ───────────────────────────────────────
        st.markdown("### Category Mix")
        cat_data = database.get_category_sales_for_date_range(
            ctx.report_loc_ids, start_str, end_str
        )
        if cat_data:
            cat_df = pd.DataFrame(cat_data)
            col_cat1, col_cat2 = st.columns(2)
            with col_cat1:
                fig_cat_bar = px.bar(
                    cat_df,
                    x="amount",
                    y="category",
                    orientation="h",
                    title="Revenue by category (₹)",
                    color="amount",
                    color_continuous_scale=[
                        ui_theme.BRAND_SUCCESS,
                        ui_theme.BRAND_PRIMARY,
                    ],
                )
                fig_cat_bar.update_layout(
                    xaxis_title="Amount (₹)",
                    yaxis_title="",
                    height=ui_theme.CHART_HEIGHT,
                    coloraxis_showscale=False,
                )
                st.plotly_chart(fig_cat_bar, use_container_width=True)
            with col_cat2:
                fig_cat_pie = px.pie(
                    cat_df,
                    names="category",
                    values="amount",
                    title="Category revenue mix",
                    hole=0.4,
                    color="category",
                    color_discrete_sequence=ui_theme.CHART_COLORWAY,
                )
                fig_cat_pie.update_layout(height=ui_theme.CHART_HEIGHT)
                st.plotly_chart(fig_cat_pie, use_container_width=True)
        else:
            st.caption("No category data for this period.")

        # ── Top Selling Items ────────────────────────────────────
        st.markdown("### Top Selling Items")
        top_items_data = database.get_top_items_for_date_range(
            ctx.report_loc_ids, start_str, end_str, limit=15
        )
        if top_items_data:
            items_df = pd.DataFrame(top_items_data)
            col_items1, col_items2 = st.columns([3, 2])
            with col_items1:
                fig_items = px.bar(
                    items_df,
                    x="amount",
                    y="item_name",
                    orientation="h",
                    title="Top 15 items by revenue (₹)",
                    color="amount",
                    color_continuous_scale=[
                        ui_theme.BRAND_SUCCESS,
                        ui_theme.BRAND_PRIMARY,
                    ],
                )
                fig_items.update_layout(
                    xaxis_title="Revenue (₹)",
                    yaxis_title="",
                    height=420,
                    coloraxis_showscale=False,
                    yaxis={"categoryorder": "total ascending"},
                )
                st.plotly_chart(fig_items, use_container_width=True)
            with col_items2:
                items_tbl = items_df.copy()
                items_tbl["amount"] = [
                    utils.format_currency(float(x or 0)) for x in items_tbl["amount"]
                ]
                items_tbl["qty"] = [f"{int(x or 0):,}" for x in items_tbl["qty"]]
                items_tbl = items_tbl.rename(
                    columns={
                        "item_name": "Item",
                        "amount": "Revenue",
                        "qty": "Qty",
                    }
                )
                st.dataframe(
                    items_tbl,
                    use_container_width=True,
                    hide_index=True,
                )
        else:
            st.caption(
                "No item-level data for this period. "
                "Re-import your Item Reports to populate top sellers."
            )

        # ── Meal Period (Service) Charts ─────────────────────────
        st.markdown("### Meal Period Breakdown")
        daily_svc = database.get_daily_service_sales_for_date_range(
            ctx.report_loc_ids, start_str, end_str
        )
        period_svc = database.get_service_sales_for_date_range(
            ctx.report_loc_ids, start_str, end_str
        )
        if daily_svc and period_svc:
            svc_daily_df = pd.DataFrame(daily_svc)
            svc_period_df = pd.DataFrame(period_svc)
            col_svc1, col_svc2 = st.columns(2)
            with col_svc1:
                fig_svc_stack = px.bar(
                    svc_daily_df,
                    x="date",
                    y="amount",
                    color="service_type",
                    barmode="stack",
                    title="Lunch vs Dinner revenue per day",
                    color_discrete_map={
                        "Lunch": ui_theme.BRAND_SECONDARY,  # #3FA7A3 — teal
                        "Dinner": ui_theme.BRAND_PRIMARY,  # #1F5FA8 — deep blue
                        "Breakfast": ui_theme.BRAND_WARN,  # #F4B400 — golden mustard
                    },
                )
                fig_svc_stack.update_layout(
                    xaxis_title="Date",
                    yaxis_title="Amount (₹)",
                    height=ui_theme.CHART_HEIGHT,
                    legend_title="Service",
                )
                st.plotly_chart(fig_svc_stack, use_container_width=True)
            with col_svc2:
                fig_svc_tot = px.bar(
                    svc_period_df,
                    x="service_type",
                    y="amount",
                    title="Total revenue by meal period",
                    color="service_type",
                    color_discrete_map={
                        "Lunch": ui_theme.BRAND_SECONDARY,  # #3FA7A3 — teal
                        "Dinner": ui_theme.BRAND_PRIMARY,  # #1F5FA8 — deep blue
                        "Breakfast": ui_theme.BRAND_WARN,  # #F4B400 — golden mustard
                    },
                )
                fig_svc_tot.update_layout(
                    xaxis_title="",
                    yaxis_title="Amount (₹)",
                    height=ui_theme.CHART_HEIGHT,
                    showlegend=False,
                )
                st.plotly_chart(fig_svc_tot, use_container_width=True)
        else:
            st.caption("No meal-period data for this period.")

        # ── Weekday Analysis ─────────────────────────────────────
        st.markdown("### Weekday Analysis")
        if len(df) >= 3:
            wd_df = df[df["net_total"] > 0].copy()
            wd_df["weekday"] = wd_df["date"].apply(utils.get_weekday_name)
            wd_agg = (
                wd_df.groupby("weekday")["net_total"]
                .mean()
                .reset_index()
                .rename(columns={"net_total": "avg_sales"})
            )
            day_order = [
                "Monday",
                "Tuesday",
                "Wednesday",
                "Thursday",
                "Friday",
                "Saturday",
                "Sunday",
            ]
            wd_agg["weekday"] = pd.Categorical(
                wd_agg["weekday"], categories=day_order, ordered=True
            )
            wd_agg = wd_agg.sort_values("weekday")
            _monthly_tgt = scope.sum_location_monthly_targets(ctx.report_loc_ids)
            _daily_tgt = (
                _monthly_tgt
                / utils.get_days_in_month(start_date.year, start_date.month)
                if _monthly_tgt > 0
                else 0
            )
            wd_colors = [
                ui_theme.BRAND_SUCCESS
                if v >= _daily_tgt
                else ui_theme.BRAND_WARN
                if v >= _daily_tgt * 0.8
                else ui_theme.BRAND_ERROR
                for v in wd_agg["avg_sales"]
            ]
            fig_wd = px.bar(
                wd_agg,
                x="weekday",
                y="avg_sales",
                title="Average net sales by day of week",
            )
            fig_wd.update_traces(marker_color=wd_colors)
            if _daily_tgt > 0:
                fig_wd.add_hline(
                    y=_daily_tgt,
                    line_dash="dash",
                    line_color="gray",
                    annotation_text=f"Daily target {utils.format_currency(_daily_tgt)}",
                    annotation_position="top right",
                )
            fig_wd.update_layout(
                xaxis_title="",
                yaxis_title="Avg Net Sales (₹)",
                height=ui_theme.CHART_HEIGHT,
            )
            st.plotly_chart(fig_wd, use_container_width=True)
        else:
            st.caption("Need at least 3 days of data for weekday analysis.")

        # ── Target Achievement ───────────────────────────────────
        st.markdown("### Target Achievement")
        monthly_target = scope.sum_location_monthly_targets(ctx.report_loc_ids)
        if monthly_target > 0:
            days_in_month = utils.get_days_in_month(start_date.year, start_date.month)
            daily_target = monthly_target / days_in_month

            fig_target = make_subplots(
                rows=1,
                cols=2,
                subplot_titles=["Daily Achievement %", "Cumulative vs Target"],
                specs=[[{"type": "bar"}, {"type": "scatter"}]],
            )

            df["achievement"] = (
                df["net_total"] / daily_target * 100 if daily_target > 0 else 0
            )
            colors = [
                ui_theme.BRAND_SUCCESS
                if x >= 100
                else ui_theme.BRAND_WARN
                if x >= 80
                else ui_theme.BRAND_ERROR
                for x in df["achievement"]
            ]
            fig_target.add_trace(
                go.Bar(
                    x=df["date"],
                    y=df["achievement"],
                    marker_color=colors,
                    name="Achievement %",
                ),
                row=1,
                col=1,
            )

            df_sorted = df.sort_values("date")
            df_sorted["cumulative"] = df_sorted["net_total"].cumsum()
            target_line = [
                monthly_target * (i / len(df_sorted))
                for i in range(1, len(df_sorted) + 1)
            ]
            fig_target.add_trace(
                go.Scatter(
                    x=df_sorted["date"],
                    y=df_sorted["cumulative"],
                    mode="lines+markers",
                    name="Actual",
                ),
                row=1,
                col=2,
            )
            fig_target.add_trace(
                go.Scatter(
                    x=df_sorted["date"],
                    y=target_line,
                    mode="lines",
                    name="Target",
                    line=dict(dash="dash"),
                ),
                row=1,
                col=2,
            )
            fig_target.update_layout(height=ui_theme.CHART_HEIGHT, showlegend=True)
            st.plotly_chart(fig_target, use_container_width=True)

            # ── Daily Data Table ─────────────────────────────────────
            st.markdown("### Daily Data")
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
                dv["covers"] = [f"{int(x or 0):,}" for x in dv["covers"]]
                dv["net_total"] = [
                    utils.format_currency(float(x or 0)) for x in dv["net_total"]
                ]
                dv["target"] = [
                    utils.format_currency(float(x or 0)) for x in dv["target"]
                ]
                dv["pct_target"] = [
                    utils.format_percent(float(x or 0)) for x in dv["pct_target"]
                ]
            st.dataframe(
                dv,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "date": st.column_config.TextColumn("Date"),
                    "Outlet": st.column_config.TextColumn("Outlet"),
                    "covers": st.column_config.TextColumn("Covers"),
                    "net_total": st.column_config.TextColumn("Net Sales (₹)"),
                    "target": st.column_config.TextColumn("Target (₹)"),
                    "pct_target": st.column_config.TextColumn("Achievement"),
                },
            )
        else:
            daily_view = df[
                ["date", "covers", "net_total", "target", "pct_target"]
            ].copy()
            daily_view["covers"] = [f"{int(x or 0):,}" for x in daily_view["covers"]]
            daily_view["net_total"] = [
                utils.format_currency(float(x or 0)) for x in daily_view["net_total"]
            ]
            daily_view["target"] = [
                utils.format_currency(float(x or 0)) for x in daily_view["target"]
            ]
            daily_view["pct_target"] = [
                utils.format_percent(float(x or 0)) for x in daily_view["pct_target"]
            ]
            st.dataframe(
                daily_view,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "date": st.column_config.TextColumn("Date"),
                    "covers": st.column_config.TextColumn("Covers"),
                    "net_total": st.column_config.TextColumn("Net Sales (₹)"),
                    "target": st.column_config.TextColumn("Target (₹)"),
                    "pct_target": st.column_config.TextColumn("Achievement"),
                },
            )

    else:
        st.info(
            "No data in this period. Upload POS files from the **Upload** tab "
            "or choose a different time range."
        )
