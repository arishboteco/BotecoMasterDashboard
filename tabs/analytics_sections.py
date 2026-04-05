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
from tabs.forecasting import linear_forecast, moving_average


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
    prior_df: pd.DataFrame = pd.DataFrame(),
) -> None:
    with st.expander("💰 Sales Performance", expanded=True):
        col_chart1, col_chart2 = st.columns(2)

        # ── Daily Sales Trend ──────────────────────────────────
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
                dates = pd.to_datetime(df["date"])
                values = df["net_total"].tolist()
                ma_values = moving_average(values, window=7)

                fig_line = go.Figure()

                # Actual sales line
                fig_line.add_trace(
                    go.Scatter(
                        x=dates,
                        y=values,
                        mode="lines+markers",
                        name="Daily Sales",
                        line=dict(color=ui_theme.BRAND_PRIMARY, width=2),
                        marker=dict(size=5),
                    )
                )

                # 7-day moving average
                ma_series = pd.Series(ma_values)
                ma_valid = ma_series[pd.notna(ma_series)]
                if not ma_valid.empty:
                    fig_line.add_trace(
                        go.Scatter(
                            x=dates[pd.notna(ma_series)],
                            y=ma_valid.tolist(),
                            mode="lines",
                            name="7-day MA",
                            line=dict(
                                color=ui_theme.BRAND_PRIMARY, width=1.5, dash="dot"
                            ),
                            opacity=0.6,
                        )
                    )

                # Forecast
                forecast_days = max(len(values) // 2, 3)
                forecast = linear_forecast(dates, values, forecast_days=forecast_days)
                if forecast:
                    f_dates = [f["date"] for f in forecast]
                    f_values = [f["value"] for f in forecast]
                    f_upper = [f["upper"] for f in forecast]
                    f_lower = [f["lower"] for f in forecast]

                    # Forecast line
                    fig_line.add_trace(
                        go.Scatter(
                            x=f_dates,
                            y=f_values,
                            mode="lines",
                            name="Forecast",
                            line=dict(
                                color=ui_theme.BRAND_PRIMARY, width=2, dash="dash"
                            ),
                            opacity=0.6,
                        )
                    )

                    # Forecast band
                    fig_line.add_trace(
                        go.Scatter(
                            x=f_dates + f_dates[::-1],
                            y=f_upper + f_lower[::-1],
                            fill="toself",
                            fillcolor="rgba(31,95,168,0.15)",
                            line=dict(color="transparent"),
                            name="Forecast Range",
                            showlegend=False,
                            hoverinfo="skip",
                        )
                    )

            fig_line.update_layout(
                xaxis_title="Date",
                yaxis_title="Net Sales (₹)",
                hovermode="x unified",
                height=ui_theme.CHART_HEIGHT,
            )
            st.plotly_chart(fig_line, use_container_width=True)

        # ── Covers Trend ───────────────────────────────────────
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
                dates = pd.to_datetime(df["date"])
                covers = df["covers"].tolist()

                fig_bar = go.Figure()

                # Actual covers bars
                fig_bar.add_trace(
                    go.Bar(
                        x=dates,
                        y=covers,
                        name="Covers",
                        marker_color=ui_theme.BRAND_SUCCESS,
                    )
                )

                # Forecast bars
                forecast_days = max(len(covers) // 2, 3)
                forecast = linear_forecast(dates, covers, forecast_days=forecast_days)
                if forecast:
                    f_dates = [f["date"] for f in forecast]
                    f_values = [max(0, f["value"]) for f in forecast]
                    fig_bar.add_trace(
                        go.Bar(
                            x=f_dates,
                            y=f_values,
                            name="Forecast",
                            marker_color=ui_theme.BRAND_SUCCESS,
                            opacity=0.4,
                        )
                    )

            fig_bar.update_layout(
                xaxis_title="Date",
                yaxis_title="Covers",
                height=ui_theme.CHART_HEIGHT,
            )
            st.plotly_chart(fig_bar, use_container_width=True)

        # ── APC Trend ──────────────────────────────────────────
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
    # ── Category Mix ───────────────────────────────────────────
    st.markdown("### Category Mix")
    cat_data = database.get_category_sales_for_date_range(
        report_loc_ids, start_str, end_str
    )
    if cat_data:
        cat_df = pd.DataFrame(cat_data)
        total_cat = float(cat_df["amount"].sum())
        fig_cat_pie = px.pie(
            cat_df,
            names="category",
            values="amount",
            title=f"Category revenue mix (Total: {utils.format_currency(total_cat)})",
            hole=0.4,
            color="category",
            color_discrete_sequence=ui_theme.CHART_COLORWAY,
        )
        fig_cat_pie.update_traces(
            textposition="inside",
            textinfo="percent+label",
        )
        fig_cat_pie.update_layout(height=ui_theme.CHART_HEIGHT)
        st.plotly_chart(fig_cat_pie, use_container_width=True)
    else:
        st.caption("No category data for this period.")

    # ── Weekday Analysis ───────────────────────────────────────
    if len(df) >= 3:
        st.markdown("### Weekday Analysis")
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
        days_in_mo = utils.get_days_in_month(start_date.year, start_date.month)
        daily_tgt = monthly_tgt / days_in_mo if monthly_tgt > 0 else 0
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

        # Best/worst day annotations
        if not wd_agg.empty:
            best_idx = wd_agg["avg_sales"].idxmax()
            worst_idx = wd_agg["avg_sales"].idxmin()
            best_day = wd_agg.loc[best_idx, "weekday"]
            best_val = wd_agg.loc[best_idx, "avg_sales"]
            worst_day = wd_agg.loc[worst_idx, "weekday"]
            worst_val = wd_agg.loc[worst_idx, "avg_sales"]
            fig_wd.add_annotation(
                x=best_day,
                y=best_val,
                text=f"Best: {best_day}",
                showarrow=True,
                arrowhead=2,
                bgcolor=ui_theme.BRAND_SUCCESS,
                font_color="white",
            )
            fig_wd.add_annotation(
                x=worst_day,
                y=worst_val,
                text=f"Worst: {worst_day}",
                showarrow=True,
                arrowhead=2,
                bgcolor=ui_theme.BRAND_ERROR,
                font_color="white",
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
    monthly_target = scope.sum_location_monthly_targets(report_loc_ids)
    if monthly_target > 0:
        st.markdown("### Target Achievement")
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

        # Determine fill color based on on-track status
        actual_last = df_sorted["cumulative"].iloc[-1]
        target_last = target_line[-1]
        fill_color = (
            "rgba(63,167,163,0.2)"
            if actual_last >= target_last
            else "rgba(239,68,68,0.2)"
        )

        fig_target.add_trace(
            go.Scatter(
                x=df_sorted["date"],
                y=df_sorted["cumulative"],
                mode="lines+markers",
                name="Actual",
                fill="tozeroy",
                fillcolor=fill_color,
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
                line=dict(dash="dash", color="gray"),
            ),
            row=1,
            col=2,
        )

        # Projected month-end extension
        last_date = pd.Timestamp(df_sorted["date"].iloc[-1])
        month_end = pd.Timestamp(start_date.replace(day=days_in_month))
        if last_date < month_end and len(df_sorted) >= 3:
            cum_values = df_sorted["cumulative"].tolist()
            cum_dates = pd.to_datetime(df_sorted["date"])
            forecast = linear_forecast(cum_dates, cum_values, forecast_days=5)
            if forecast:
                f_dates = [f["date"] for f in forecast if f["date"] <= month_end]
                f_values = [f["value"] for f in forecast if f["date"] <= month_end]
                if f_dates:
                    fig_target.add_trace(
                        go.Scatter(
                            x=f_dates,
                            y=f_values,
                            mode="lines",
                            name="Projected",
                            line=dict(dash="dot", color=ui_theme.BRAND_PRIMARY),
                            opacity=0.6,
                        ),
                        row=1,
                        col=2,
                    )

        fig_target.update_layout(height=ui_theme.CHART_HEIGHT, showlegend=True)
        st.plotly_chart(fig_target, use_container_width=True)

        # On-track / Behind badge
        if actual_last >= target_last:
            st.success(
                f"✅ **On track** — {utils.format_currency(actual_last - target_last)} ahead of target pace"
            )
        else:
            st.error(
                f"⚠️ **Behind by {utils.format_currency(target_last - actual_last)}** — below target pace"
            )

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
