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
from tabs.forecasting import (
    calculate_forecast_days,
    linear_forecast,
    moving_average,
)


def _hex_to_rgba(hex_color: str, alpha: float = 0.2) -> str:
    """Convert a hex color to rgba string with given alpha."""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


def _fmt_rupee_hover(values: list, name: str = "%{x|%b %d}") -> dict:
    """Build customdata + hovertemplate for Indian ₹ formatting on a Plotly trace.

    Returns dict with 'customdata' and 'hovertemplate' keys to unpack into
    go.Scatter(...).  Hover shows: "Apr 05: ₹1,30,235".
    """
    formatted = [utils.format_indian_currency(float(v)) for v in values]
    return {
        "customdata": formatted,
        "hovertemplate": name + ": %{customdata}<extra></extra>",
    }


def _fmt_int_hover(values: list, name: str = "%{x|%b %d}") -> dict:
    """Build hovertemplate for integer values (covers, counts).

    Hover shows: "Apr 05: 72".
    """
    formatted = [f"{int(v):,}" for v in values]
    return {
        "customdata": formatted,
        "hovertemplate": name + ": %{customdata}<extra></extra>",
    }


def _rupee_yaxis() -> dict:
    """Return xaxis/yaxis config that formats sales ticks as ₹1L, ₹2L etc."""
    return dict(
        tickprefix="₹",
        tickformat=",.0f",
    )


def _period_supports_trend_analysis(period: str, data_points: int) -> bool:
    """Return True if the selected period has enough data for MA and forecast.

    Moving average requires at least 3 data points. Forecast will show with ±1 std dev
    bands even with minimal data; confidence band widens for short datasets.
    """
    _long_periods = {"Last 7 Days", "Last 30 Days", "Last Month", "Custom"}
    if period in _long_periods:
        return data_points >= 3
    return False


def _chart_summary(text: str) -> None:
    """Render a screen-reader-friendly text summary of a chart's key insight."""
    st.caption(text)


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
    analysis_period: str = "",
) -> None:
    show_ma_and_forecast = _period_supports_trend_analysis(analysis_period, len(df))

    with st.expander("💰 Sales Performance", expanded=True):
        col_chart1, col_chart2 = st.columns(2)

        # ── Daily Sales Trend ──────────────────────────────────
        with col_chart1:
            st.markdown("### Daily Sales Trend")
            if multi_analytics and not df_raw.empty:
                fig_line = go.Figure()
                for outlet_name in df_raw["Outlet"].unique():
                    odf = df_raw[df_raw["Outlet"] == outlet_name].sort_values("date")
                    hover = _fmt_rupee_hover(odf["net_total"].tolist(), outlet_name)
                    fig_line.add_trace(
                        go.Scatter(
                            x=pd.to_datetime(odf["date"]),
                            y=odf["net_total"].tolist(),
                            mode="lines+markers",
                            name=outlet_name,
                            marker=dict(size=4),
                            **hover,
                        )
                    )
                # Add 7-day MA per outlet as dashed lines
                if show_ma_and_forecast:
                    outlet_colors = {
                        trace.name: trace.line.color
                        if hasattr(trace.line, "color")
                        else None
                        for trace in fig_line.data
                    }
                    for outlet_name in df_raw["Outlet"].unique():
                        outlet_df = df_raw[df_raw["Outlet"] == outlet_name].sort_values(
                            "date"
                        )
                        outlet_values = outlet_df["net_total"].tolist()
                        outlet_dates = pd.to_datetime(outlet_df["date"])

                        ma_vals = moving_average(outlet_values, window=7)
                        ma_series = pd.Series(ma_vals)
                        ma_valid = ma_series[pd.notna(ma_series)]
                        if not ma_valid.empty:
                            ma_color = outlet_colors.get(outlet_name, "#FF6B35")
                            fig_line.add_trace(
                                go.Scatter(
                                    x=outlet_dates[pd.notna(ma_series)],
                                    y=ma_valid.tolist(),
                                    mode="lines",
                                    name=f"{outlet_name} 7-day Avg",
                                    line=dict(color=ma_color, width=2, dash="dash"),
                                    opacity=0.7,
                                    showlegend=False,
                                )
                            )

                        forecast_days = calculate_forecast_days(
                            analysis_period, len(outlet_values)
                        )
                        forecast = linear_forecast(
                            outlet_dates,
                            outlet_values,
                            forecast_days=forecast_days,
                        )
                        if forecast:
                            f_dates = [f["date"] for f in forecast]
                            f_values = [f["value"] for f in forecast]
                            f_upper = [f["upper"] for f in forecast]
                            f_lower = [f["lower"] for f in forecast]

                            # Forecast line per outlet (overlay)
                            hover_fc = _fmt_rupee_hover(f_values, "Forecast")
                            fig_line.add_trace(
                                go.Scatter(
                                    x=f_dates,
                                    y=f_values,
                                    mode="lines",
                                    name=f"{outlet_name} Forecast",
                                    line=dict(
                                        color=ui_theme.BRAND_WARN, width=2, dash="dash"
                                    ),
                                    opacity=0.8,
                                    showlegend=False,
                                    **hover_fc,
                                )
                            )

                            # Forecast confidence band per outlet
                            fig_line.add_trace(
                                go.Scatter(
                                    x=f_dates + f_dates[::-1],
                                    y=f_upper + f_lower[::-1],
                                    fill="toself",
                                    fillcolor=_hex_to_rgba(ui_theme.BRAND_WARN, 0.25),
                                    line=dict(color="rgba(0,0,0,0)"),
                                    name="Forecast Range",
                                    showlegend=False,
                                    hoverinfo="skip",
                                )
                            )
            else:
                dates = pd.to_datetime(df["date"])
                values = df["net_total"].tolist()

                fig_line = go.Figure()

                # Actual sales area
                hover_sales = _fmt_rupee_hover(values, "Sales")
                fig_line.add_trace(
                    go.Scatter(
                        x=dates,
                        y=values,
                        mode="lines+markers",
                        name="Daily Sales",
                        fill="tozeroy",
                        fillcolor=_hex_to_rgba(ui_theme.BRAND_PRIMARY, 0.15),
                        line=dict(color=ui_theme.BRAND_PRIMARY, width=2),
                        marker=dict(size=4),
                        **hover_sales,
                    )
                )

                # 7-day moving average (only for longer periods)
                if show_ma_and_forecast:
                    ma_values = moving_average(values, window=7)
                    ma_series = pd.Series(ma_values)
                    ma_valid = ma_series[pd.notna(ma_series)]
                    if not ma_valid.empty:
                        fig_line.add_trace(
                            go.Scatter(
                                x=dates[pd.notna(ma_series)],
                                y=ma_valid.tolist(),
                                mode="lines",
                                name="7-day Avg",
                                line=dict(color="#FF6B35", width=2, dash="dash"),
                                opacity=0.7,
                            )
                        )

                    # Forecast
                    forecast_days = calculate_forecast_days(
                        analysis_period, len(values)
                    )
                    forecast = linear_forecast(
                        dates, values, forecast_days=forecast_days
                    )
                    if forecast:
                        f_dates = [f["date"] for f in forecast]
                        f_values = [f["value"] for f in forecast]
                        f_upper = [f["upper"] for f in forecast]
                        f_lower = [f["lower"] for f in forecast]

                        # Forecast line
                        hover_fc = _fmt_rupee_hover(f_values, "Forecast")
                        fig_line.add_trace(
                            go.Scatter(
                                x=f_dates,
                                y=f_values,
                                mode="lines",
                                name="Forecast",
                                line=dict(
                                    color=ui_theme.BRAND_WARN, width=2, dash="dash"
                                ),
                                opacity=0.8,
                                **hover_fc,
                            )
                        )

                        # Forecast band
                        fig_line.add_trace(
                            go.Scatter(
                                x=f_dates + f_dates[::-1],
                                y=f_upper + f_lower[::-1],
                                fill="toself",
                                fillcolor=_hex_to_rgba(ui_theme.BRAND_WARN, 0.25),
                                line=dict(color="rgba(0,0,0,0)"),
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
                xaxis=dict(tickformat="%b %d"),
                yaxis=_rupee_yaxis(),
            )
            st.plotly_chart(fig_line, use_container_width=True)

            # Screen reader summary
            if not multi_analytics and values:
                _chart_summary(
                    "Daily sales range from {} to {} across {} days.".format(
                        utils.format_currency(min(values)),
                        utils.format_currency(max(values)),
                        len(values),
                    )
                )

        # ── Covers Trend ───────────────────────────────────────
        with col_chart2:
            st.markdown("### Covers Trend")
            if multi_analytics and not df_raw.empty:
                fig_covers = go.Figure()
                for outlet_name in df_raw["Outlet"].unique():
                    outlet_df = df_raw[df_raw["Outlet"] == outlet_name].sort_values(
                        "date"
                    )
                    outlet_dates = pd.to_datetime(outlet_df["date"])
                    outlet_covers = outlet_df["covers"].tolist()

                    hover_cov = _fmt_int_hover(outlet_covers, outlet_name)
                    fig_covers.add_trace(
                        go.Bar(
                            x=outlet_dates,
                            y=outlet_covers,
                            name=outlet_name,
                            **hover_cov,
                        )
                    )

                    if show_ma_and_forecast:
                        forecast_days = calculate_forecast_days(
                            analysis_period, len(outlet_covers)
                        )
                        forecast = linear_forecast(
                            outlet_dates,
                            outlet_covers,
                            forecast_days=forecast_days,
                        )
                        if forecast:
                            f_dates = [f["date"] for f in forecast]
                            f_values = [max(0, f["value"]) for f in forecast]
                            f_upper = [f["upper"] for f in forecast]
                            f_lower = [f["lower"] for f in forecast]

                            hover_cov_fc = _fmt_int_hover(f_values, "Forecast")
                            fig_covers.add_trace(
                                go.Scatter(
                                    x=f_dates,
                                    y=f_values,
                                    mode="lines",
                                    name=f"{outlet_name} Forecast",
                                    line=dict(
                                        color=ui_theme.BRAND_INFO,
                                        width=2,
                                        dash="dash",
                                    ),
                                    opacity=0.6,
                                    showlegend=False,
                                    **hover_cov_fc,
                                )
                            )
                            fig_covers.add_trace(
                                go.Scatter(
                                    x=f_dates + f_dates[::-1],
                                    y=f_upper + f_lower[::-1],
                                    fill="toself",
                                    fillcolor=_hex_to_rgba(ui_theme.BRAND_INFO, 0.25),
                                    line=dict(color="rgba(0,0,0,0)"),
                                    name="Forecast Range",
                                    showlegend=False,
                                    hoverinfo="skip",
                                )
                            )
            else:
                dates = pd.to_datetime(df["date"])
                covers = df["covers"].tolist()

                fig_covers = go.Figure()

                # Actual covers area
                hover_cov = _fmt_int_hover(covers, "Covers")
                fig_covers.add_trace(
                    go.Scatter(
                        x=dates,
                        y=covers,
                        mode="lines+markers",
                        name="Covers",
                        fill="tozeroy",
                        fillcolor=_hex_to_rgba(ui_theme.BRAND_SUCCESS, 0.15),
                        line=dict(color=ui_theme.BRAND_SUCCESS, width=2),
                        marker=dict(size=4),
                        **hover_cov,
                    )
                )

                # Forecast area (only for longer periods)
                if show_ma_and_forecast:
                    forecast_days = calculate_forecast_days(
                        analysis_period, len(covers)
                    )
                    forecast = linear_forecast(
                        dates, covers, forecast_days=forecast_days
                    )
                    if forecast:
                        f_dates = [f["date"] for f in forecast]
                        f_values = [max(0, f["value"]) for f in forecast]
                        hover_cov_fc = _fmt_int_hover(f_values, "Forecast")
                        fig_covers.add_trace(
                            go.Scatter(
                                x=f_dates,
                                y=f_values,
                                mode="lines",
                                name="Forecast",
                                fill="tozeroy",
                                fillcolor=_hex_to_rgba(ui_theme.BRAND_INFO, 0.15),
                                line=dict(
                                    color=ui_theme.BRAND_INFO, width=2, dash="dash"
                                ),
                                opacity=0.6,
                                **hover_cov_fc,
                            )
                        )

            fig_covers.update_layout(
                xaxis_title="Date",
                yaxis_title="Covers",
                hovermode="x unified",
                height=ui_theme.CHART_HEIGHT,
                barmode="group",
                xaxis=dict(tickformat="%b %d"),
            )
            st.plotly_chart(fig_covers, use_container_width=True)

            # Screen reader summary
            if not multi_analytics and covers:
                _chart_summary(
                    "Daily covers range from {:,} to {:,} with an average of {:,}.".format(
                        min(covers),
                        max(covers),
                        sum(covers) // len(covers),
                    )
                )

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
                yaxis=dict(rangemode="tozero"),
                hovermode="x unified",
                height=ui_theme.CHART_HEIGHT,
                xaxis=dict(tickformat="%b %d"),
            )
            st.plotly_chart(fig_apc, use_container_width=True)
            _chart_summary(
                "Average per cover is {} across {} days with data.".format(
                    utils.format_currency(avg_apc),
                    len(apc_df),
                )
            )
        else:
            st.caption("No APC data for this period.")

        # ── Sales Performance drill-down table ───────────────────
        with st.expander("View data"):
            if multi_analytics and not df_raw.empty:
                _sales_tbl = df_raw[["date", "Outlet", "net_total", "covers"]].copy()
            else:
                _sales_tbl = df[["date", "net_total", "covers"]].copy()
            if "apc" in df.columns:
                if multi_analytics and not df_raw.empty:
                    _sales_tbl["apc"] = _sales_tbl.apply(
                        lambda r: (
                            r["net_total"] / r["covers"] if r["covers"] > 0 else 0
                        ),
                        axis=1,
                    )
                else:
                    _sales_tbl["apc"] = df["apc"]
            else:
                _sales_tbl["apc"] = _sales_tbl.apply(
                    lambda r: r["net_total"] / r["covers"] if r["covers"] > 0 else 0,
                    axis=1,
                )
            _sales_tbl = _sales_tbl.rename(
                columns={
                    "date": "Date",
                    "net_total": "Net Sales (₹)",
                    "covers": "Covers",
                    "apc": "APC (₹)",
                }
            )
            if "Outlet" in _sales_tbl.columns:
                _sales_tbl = _sales_tbl.sort_values(["Date", "Outlet"])
            else:
                _sales_tbl = _sales_tbl.sort_values("Date")
            _sales_tbl["Net Sales (₹)"] = _sales_tbl["Net Sales (₹)"].apply(
                lambda x: utils.format_currency(float(x))
            )
            _sales_tbl["APC (₹)"] = _sales_tbl["APC (₹)"].apply(
                lambda x: utils.format_currency(float(x))
            )
            _sales_tbl["Covers"] = _sales_tbl["Covers"].apply(lambda x: f"{int(x):,}")
            st.dataframe(_sales_tbl, use_container_width=True, hide_index=True)


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

        # Group categories <2% into "Other"
        cat_df["pct"] = cat_df["amount"] / total_cat * 100 if total_cat > 0 else 0
        small_cats = cat_df[cat_df["pct"] < 2]
        large_cats = cat_df[cat_df["pct"] >= 2].copy()
        if not small_cats.empty:
            other_amount = float(small_cats["amount"].sum())
            other_qty = int(small_cats["qty"].sum())
            other_row = pd.DataFrame(
                [
                    {
                        "category": "Other",
                        "amount": other_amount,
                        "qty": other_qty,
                        "pct": other_amount / total_cat * 100,
                    }
                ]
            )
            chart_df = pd.concat([large_cats, other_row], ignore_index=True)
        else:
            chart_df = large_cats.copy()

        n_categories = len(chart_df)

        if n_categories > 5:
            fig_cat = px.bar(
                chart_df.sort_values("amount", ascending=True),
                y="category",
                x="amount",
                orientation="h",
                title=f"Category revenue (Total: {utils.format_currency(total_cat)})",
                color="category",
                color_discrete_sequence=ui_theme.CHART_COLORWAY,
            )
            fig_cat.update_layout(
                yaxis_title="",
                xaxis_title="Revenue (₹)",
                height=max(ui_theme.CHART_HEIGHT, 60 * n_categories),
                showlegend=False,
            )
        else:
            fig_cat = px.pie(
                chart_df,
                names="category",
                values="amount",
                title=f"Category revenue mix (Total: {utils.format_currency(total_cat)})",
                hole=0.4,
                color="category",
                color_discrete_sequence=ui_theme.CHART_COLORWAY,
            )
            fig_cat.update_traces(
                textposition="inside",
                textinfo="percent+label",
            )
            fig_cat.update_layout(height=ui_theme.CHART_HEIGHT)

        st.plotly_chart(fig_cat, use_container_width=True)

        # Full category breakdown table
        _cat_table = cat_df[["category", "amount"]].copy()
        _cat_table["% of Total"] = _cat_table["amount"].apply(
            lambda x: f"{x / total_cat * 100:.1f}%" if total_cat > 0 else "0%"
        )
        _cat_table["amount"] = _cat_table["amount"].apply(
            lambda x: utils.format_currency(float(x))
        )
        _cat_table = _cat_table.rename(
            columns={"category": "Category", "amount": "Amount"}
        )
        with st.expander("View category data"):
            st.dataframe(_cat_table, use_container_width=True, hide_index=True)
    else:
        st.caption("No category data for this period.")

    # ── Weekday Analysis ───────────────────────────────────────
    # Only meaningful for periods spanning at least 7 days
    if len(df) >= 7:
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

        # Best/worst day identification for conditional coloring
        _best_idx = wd_agg["avg_sales"].idxmax()
        _worst_idx = wd_agg["avg_sales"].idxmin()
        wd_colors = []
        for i in range(len(wd_agg)):
            if i == _best_idx:
                wd_colors.append("#22c55e")
            elif i == _worst_idx:
                wd_colors.append("#ef4444")
            else:
                wd_colors.append("#6366f1")

        wd_patterns = [
            "✓" if v >= daily_tgt else "⚠" if v >= daily_tgt * 0.8 else "✗"
            for v in wd_agg["avg_sales"]
        ]
        fig_wd = px.bar(
            wd_agg,
            x="weekday",
            y="avg_sales",
            title="Average net sales by day of week",
            text=wd_patterns,
        )
        fig_wd.update_traces(
            marker_color=wd_colors,
            textposition="outside",
            textfont=dict(size=14, color=ui_theme.TEXT_PRIMARY),
        )
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
        _chart_summary(
            "Best day is {} (avg {}) and worst is {} (avg {}).".format(
                best_day,
                utils.format_currency(best_val),
                worst_day,
                utils.format_currency(worst_val),
            )
        )

        # Weekday drill-down table
        with st.expander("View data"):
            wd_covers = (
                wd_df.groupby("weekday")["covers"]
                .mean()
                .reset_index()
                .rename(columns={"covers": "avg_covers"})
            )
            wd_count = (
                wd_df.groupby("weekday")["net_total"]
                .count()
                .reset_index()
                .rename(columns={"net_total": "count_days"})
            )
            wd_table = wd_agg.merge(wd_covers, on="weekday", how="left").merge(
                wd_count, on="weekday", how="left"
            )
            wd_table["weekday"] = pd.Categorical(
                wd_table["weekday"], categories=day_order, ordered=True
            )
            wd_table = wd_table.sort_values("weekday")
            wd_table = wd_table.rename(
                columns={
                    "weekday": "Day of Week",
                    "avg_sales": "Avg Net Sales (₹)",
                    "avg_covers": "Avg Covers",
                    "count_days": "Count of Days",
                }
            )
            wd_table["Avg Net Sales (₹)"] = wd_table["Avg Net Sales (₹)"].apply(
                lambda x: utils.format_currency(float(x))
            )
            wd_table["Avg Covers"] = wd_table["Avg Covers"].apply(
                lambda x: f"{float(x):.0f}"
            )
            st.dataframe(
                wd_table[
                    ["Day of Week", "Avg Net Sales (₹)", "Avg Covers", "Count of Days"]
                ],
                use_container_width=True,
                hide_index=True,
            )
    else:
        st.caption("Need at least 7 days of data for weekday analysis.")


def render_target_and_daily(
    report_loc_ids: list[int],
    start_date: date,
    df: pd.DataFrame,
    df_raw: pd.DataFrame,
    multi_analytics: bool,
    analysis_period: str = "",
) -> None:
    monthly_target = scope.sum_location_monthly_targets(report_loc_ids)
    is_monthly_period = analysis_period in {"This Month", "Last Month", "Custom"}
    if monthly_target > 0 and is_monthly_period:
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
            _hex_to_rgba(ui_theme.BRAND_SUCCESS, 0.2)
            if actual_last >= target_last
            else _hex_to_rgba(ui_theme.BRAND_ERROR, 0.2)
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

        _chart_summary(
            "Cumulative sales are {} vs target pace of {}.".format(
                utils.format_currency(actual_last),
                utils.format_currency(target_last),
            )
        )

        # Target achievement drill-down table
        with st.expander("View data"):
            if multi_analytics and not df_raw.empty:
                _tgt_tbl = df_raw[
                    ["date", "Outlet", "net_total", "target", "pct_target"]
                ].copy()
                _tgt_tbl["pct_target"] = _tgt_tbl["pct_target"].apply(
                    lambda x: f"{float(x or 0):.0f}%"
                )
            else:
                _tgt_tbl = target_df[
                    ["date", "net_total", "target", "achievement"]
                ].copy()
                _tgt_tbl["achievement"] = _tgt_tbl["achievement"].apply(
                    lambda x: f"{float(x or 0):.0f}%"
                )
                _tgt_tbl = _tgt_tbl.rename(columns={"achievement": "pct_target"})
            _tgt_tbl = _tgt_tbl.rename(
                columns={
                    "date": "Date",
                    "net_total": "Net Sales (₹)",
                    "target": "Target (₹)",
                    "pct_target": "Achievement",
                }
            )
            _tgt_tbl["Net Sales (₹)"] = _tgt_tbl["Net Sales (₹)"].apply(
                lambda x: utils.format_currency(float(x))
            )
            _tgt_tbl["Target (₹)"] = _tgt_tbl["Target (₹)"].apply(
                lambda x: utils.format_currency(float(x))
            )
            st.dataframe(_tgt_tbl, use_container_width=True, hide_index=True)

        st.markdown("### Daily Data")
        dv = build_daily_view_table(df, df_raw, multi_analytics, numeric=True)

        def _style_achievement(val):
            if pd.isna(val):
                return ""
            if val >= 100:
                return "background-color: #dcfce7; color: #166534"
            elif val >= 70:
                return "background-color: #fef9c3; color: #854d0e"
            else:
                return "background-color: #fee2e2; color: #991b1b"

        dv_display = dv.copy()
        _is_multi_table = "Outlet" in dv_display.columns
        rename_map = {
            "date": "Date",
            "covers": "Covers",
            "net_total": "Net Sales (₹)",
            "target": "Target (₹)",
            "pct_target": "Achievement %",
        }
        if _is_multi_table:
            rename_map["Outlet"] = "Outlet"
        dv_display = dv_display.rename(columns=rename_map)

        styler = dv_display.style.map(
            _style_achievement, subset=["Achievement %"]
        ).format(
            {
                "Covers": "{:,.0f}",
                "Net Sales (₹)": lambda x: utils.format_indian_currency(float(x)),
                "Target (₹)": lambda x: utils.format_indian_currency(float(x)),
                "Achievement %": "{:.1f}%",
            },
            na_rep="",
        )
        # Bold the total row
        _total_row_idx = len(dv_display) - 1
        styler = styler.set_properties(
            subset=pd.IndexSlice[_total_row_idx, :],
            **{"font-weight": "bold"},
        )
        st.dataframe(styler, use_container_width=True, hide_index=True)
    else:
        daily_view = build_daily_view_table(
            df, pd.DataFrame(), multi_analytics=False, numeric=True
        )

        def _style_achievement(val):
            if pd.isna(val):
                return ""
            if val >= 100:
                return "background-color: #dcfce7; color: #166534"
            elif val >= 70:
                return "background-color: #fef9c3; color: #854d0e"
            else:
                return "background-color: #fee2e2; color: #991b1b"

        dv_display = daily_view.rename(
            columns={
                "date": "Date",
                "covers": "Covers",
                "net_total": "Net Sales (₹)",
                "target": "Target (₹)",
                "pct_target": "Achievement %",
            }
        )
        styler = dv_display.style.map(
            _style_achievement, subset=["Achievement %"]
        ).format(
            {
                "Covers": "{:,.0f}",
                "Net Sales (₹)": lambda x: utils.format_indian_currency(float(x)),
                "Target (₹)": lambda x: utils.format_indian_currency(float(x)),
                "Achievement %": "{:.1f}%",
            },
            na_rep="",
        )
        _total_row_idx = len(dv_display) - 1
        styler = styler.set_properties(
            subset=pd.IndexSlice[_total_row_idx, :],
            **{"font-weight": "bold"},
        )
        st.dataframe(styler, use_container_width=True, hide_index=True)
