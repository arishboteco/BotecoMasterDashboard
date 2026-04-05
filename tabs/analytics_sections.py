"""Section render helpers for analytics tab."""

from __future__ import annotations

from datetime import date

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

import database
import scope
import ui_theme
import utils
from tabs.analytics_logic import build_daily_view_table


def _daily_table_column_config() -> dict:
    return {
        "date": st.column_config.TextColumn("Date"),
        "covers": st.column_config.TextColumn("Covers"),
        "net_total": st.column_config.TextColumn("Net Sales (₹)"),
        "target": st.column_config.TextColumn("Target (₹)"),
        "pct_target": st.column_config.TextColumn("Achievement"),
    }


def render_overview(
    analysis_period: str,
    start_date: date,
    total_sales: float,
    avg_daily: float,
    total_covers: int,
    days_with_data: int,
    prior_total: float | None,
    prior_covers: int | None,
    prior_avg: float | None,
) -> None:
    with st.expander("📊 Overview", expanded=True):
        st.markdown("### Period Summary")
        with st.container(border=True):
            show_projection = analysis_period == "This Month"
            ncols = 5 if show_projection else 4
            kpi_cols = st.columns(ncols)

            def _delta_str(current, prior):
                if prior is None or prior == 0:
                    return None
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
                days_in_mo = utils.get_days_in_month(start_date.year, start_date.month)
                projected = utils.calculate_projected_sales(
                    total_sales,
                    days_with_data,
                    days_in_mo,
                )
                with kpi_cols[4]:
                    st.metric(
                        "Projected Month-End",
                        utils.format_currency(projected),
                        help="Based on current run rate extrapolated to end of month.",
                    )


def render_sales_performance(
    df: pd.DataFrame,
    df_raw: pd.DataFrame,
    multi_analytics: bool,
) -> None:
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


def render_revenue_breakdown(
    report_loc_ids: list[int],
    start_str: str,
    end_str: str,
    df: pd.DataFrame,
    start_date: date,
) -> None:
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
                "Cash": ui_theme.BRAND_PRIMARY,
                "GPay": ui_theme.BRAND_SECONDARY,
                "Zomato": ui_theme.BRAND_GREEN,
                "Card": ui_theme.BRAND_WARN,
                "Other": ui_theme.BRAND_DARK,
            },
        )
        fig_pay.update_layout(
            xaxis_title="Amount (₹)",
            yaxis_title="",
            height=ui_theme.CHART_HEIGHT,
            showlegend=False,
        )
        st.plotly_chart(fig_pay, use_container_width=True)

    st.markdown("### Category Mix")
    cat_data = database.get_category_sales_for_date_range(
        report_loc_ids, start_str, end_str
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

    st.markdown("### Top Selling Items")
    top_items_data = database.get_top_items_for_date_range(
        report_loc_ids, start_str, end_str, limit=15
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

    st.markdown("### Meal Period Breakdown")
    daily_svc = database.get_daily_service_sales_for_date_range(
        report_loc_ids, start_str, end_str
    )
    period_svc = database.get_service_sales_for_date_range(
        report_loc_ids, start_str, end_str
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
                    "Lunch": ui_theme.BRAND_SECONDARY,
                    "Dinner": ui_theme.BRAND_PRIMARY,
                    "Breakfast": ui_theme.BRAND_WARN,
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
                    "Lunch": ui_theme.BRAND_SECONDARY,
                    "Dinner": ui_theme.BRAND_PRIMARY,
                    "Breakfast": ui_theme.BRAND_WARN,
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
        monthly_tgt = scope.sum_location_monthly_targets(report_loc_ids)
        daily_tgt = (
            monthly_tgt / utils.get_days_in_month(start_date.year, start_date.month)
            if monthly_tgt > 0
            else 0
        )
        wd_colors = [
            ui_theme.BRAND_SUCCESS
            if v >= daily_tgt
            else ui_theme.BRAND_WARN
            if v >= daily_tgt * 0.8
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
        if daily_tgt > 0:
            fig_wd.add_hline(
                y=daily_tgt,
                line_dash="dash",
                line_color="gray",
                annotation_text=f"Daily target {utils.format_currency(daily_tgt)}",
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


def render_target_and_daily(
    report_loc_ids: list[int],
    start_date: date,
    df: pd.DataFrame,
    df_raw: pd.DataFrame,
    multi_analytics: bool,
) -> None:
    st.markdown("### Target Achievement")
    monthly_target = scope.sum_location_monthly_targets(report_loc_ids)
    if monthly_target > 0:
        days_in_month = utils.get_days_in_month(start_date.year, start_date.month)
        daily_target = monthly_target / days_in_month

        fig_target = make_subplots(
            rows=1,
            cols=2,
            subplot_titles=["Daily Achievement %", "Cumulative vs Target"],
            specs=[[{"type": "bar"}, {"type": "scatter"}]],
        )

        target_df = df.copy()
        target_df["achievement"] = (
            target_df["net_total"] / daily_target * 100 if daily_target > 0 else 0
        )
        colors = [
            ui_theme.BRAND_SUCCESS
            if x >= 100
            else ui_theme.BRAND_WARN
            if x >= 80
            else ui_theme.BRAND_ERROR
            for x in target_df["achievement"]
        ]
        fig_target.add_trace(
            go.Bar(
                x=target_df["date"],
                y=target_df["achievement"],
                marker_color=colors,
                name="Achievement %",
            ),
            row=1,
            col=1,
        )

        df_sorted = target_df.sort_values("date")
        df_sorted["cumulative"] = df_sorted["net_total"].cumsum()
        target_line = [
            monthly_target * (i / len(df_sorted)) for i in range(1, len(df_sorted) + 1)
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

        st.markdown("### Daily Data")
        dv = build_daily_view_table(df, df_raw, multi_analytics)
        st.dataframe(
            dv,
            use_container_width=True,
            hide_index=True,
            column_config=_daily_table_column_config(),
        )
    else:
        daily_view = build_daily_view_table(df, pd.DataFrame(), multi_analytics=False)
        st.dataframe(
            daily_view,
            use_container_width=True,
            hide_index=True,
            column_config=_daily_table_column_config(),
        )
