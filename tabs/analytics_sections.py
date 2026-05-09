"""Section render helpers for analytics tab."""

from __future__ import annotations

from datetime import date

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

import database
import scope
import ui_theme
import utils
from components import KpiMetric, kpi_row
from tabs.analytics_logic import build_daily_view_table
from tabs.chart_builders import _hex_to_rgba, _period_supports_trend_analysis
from tabs.forecasting import (
    calculate_forecast_days,
    linear_forecast,
    moving_average,
)


def _build_action_cards(
    current_df: pd.DataFrame,
    prior_df: pd.DataFrame,
    monthly_target: float,
    forecast_total: float,
) -> list[dict[str, str]]:
    """Build ranked, explainable action cards from available signals."""
    cards: list[dict[str, str]] = []

    if current_df.empty:
        return cards

    current_sales = float(pd.to_numeric(current_df["net_total"], errors="coerce").fillna(0).sum())
    current_covers = float(pd.to_numeric(current_df["covers"], errors="coerce").fillna(0).sum())
    current_apc = current_sales / current_covers if current_covers > 0 else 0.0

    prior_sales = 0.0
    prior_covers = 0.0
    prior_apc = 0.0
    if not prior_df.empty:
        prior_sales = float(pd.to_numeric(prior_df["net_total"], errors="coerce").fillna(0).sum())
        prior_covers = float(pd.to_numeric(prior_df["covers"], errors="coerce").fillna(0).sum())
        prior_apc = prior_sales / prior_covers if prior_covers > 0 else 0.0

    if monthly_target > 0 and forecast_total > 0 and forecast_total < monthly_target:
        gap = monthly_target - forecast_total
        cards.append(
            {
                "severity": "high",
                "title": "Target at Risk",
                "reason": (
                    f"Forecast projects {utils.format_rupee_short(forecast_total)} vs "
                    f"target {utils.format_rupee_short(monthly_target)}."
                ),
                "action": "Push high-conversion bundles on peak hours and monitor daily pace.",
                "metric": f"Gap: {utils.format_rupee_short(gap)}",
            }
        )

    if prior_sales > 0:
        sales_change = ((current_sales - prior_sales) / prior_sales) * 100
        if sales_change <= -8:
            cards.append(
                {
                    "severity": "high",
                    "title": "Sales Trend Softening",
                    "reason": f"Sales are {sales_change:.1f}% below previous period.",
                    "action": (
                        "Audit low days and launch a short tactical promo "
                        "for demand recovery."
                    ),
                    "metric": f"Delta: {sales_change:.1f}%",
                }
            )
        elif sales_change >= 8:
            cards.append(
                {
                    "severity": "medium",
                    "title": "Momentum Opportunity",
                    "reason": f"Sales are {sales_change:.1f}% above previous period.",
                    "action": (
                        "Protect momentum by keeping top categories in stock "
                        "and staffing peak slots."
                    ),
                    "metric": f"Delta: +{sales_change:.1f}%",
                }
            )

    if prior_covers > 0 and prior_apc > 0:
        covers_change = ((current_covers - prior_covers) / prior_covers) * 100
        apc_change = ((current_apc - prior_apc) / prior_apc) * 100
        if covers_change >= 8 and apc_change <= -8:
            cards.append(
                {
                    "severity": "high",
                    "title": "APC Under Pressure",
                    "reason": (
                        f"Covers are +{covers_change:.1f}% but APC is "
                        f"{apc_change:.1f}% vs previous period."
                    ),
                    "action": (
                        "Prioritize upsell scripts and premium pairings "
                        "to recover ticket size."
                    ),
                    "metric": f"APC: {utils.format_currency(current_apc)}",
                }
            )

    if not cards:
        cards.append(
            {
                "severity": "low",
                "title": "Stable Performance",
                "reason": "No major risk signal detected from forecast and prior-period deltas.",
                "action": (
                    "Maintain current run-rate and continue monitoring "
                    "weekday/category shifts."
                ),
                "metric": "Signal: Neutral",
            }
        )

    severity_rank = {"high": 0, "medium": 1, "low": 2}
    cards = sorted(cards, key=lambda c: severity_rank.get(c["severity"], 3))
    return cards[:3]


def _style_achievement(val) -> str:
    """Pandas Styler.map function: color an Achievement % cell by band."""
    if pd.isna(val):
        return ""
    if val >= 100:
        return (
            f"background-color: {ui_theme.ACHIEVEMENT_HIGH_BG}; "
            f"color: {ui_theme.ACHIEVEMENT_HIGH_TEXT}"
        )
    if val >= 70:
        return (
            f"background-color: {ui_theme.ACHIEVEMENT_MED_BG}; "
            f"color: {ui_theme.ACHIEVEMENT_MED_TEXT}"
        )
    return (
        f"background-color: {ui_theme.ACHIEVEMENT_LOW_BG}; "
        f"color: {ui_theme.ACHIEVEMENT_LOW_TEXT}"
    )


def _fmt_rupee_short(amount: float) -> str:
    """Format a rupee amount as a short label: ₹1.3k, ₹130k, ₹1.3L.

    Uses 1 decimal place for clarity (e.g., ₹1.3L not ₹1.27L).
    """
    abs_amt = abs(amount)
    sign = "-" if amount < 0 else ""
    if abs_amt >= 1_00_000:
        lakhs = abs_amt / 1_00_000
        return f"{sign}₹{lakhs:.1f}L"
    elif abs_amt >= 1_000:
        k = abs_amt / 1_000
        return f"{sign}₹{k:.1f}k"
    else:
        return f"{sign}₹{abs_amt:.0f}"


def _fmt_rupee_hover(values: list, name: str = "%{x|%b %d}") -> dict:
    """Build customdata + hovertemplate for ₹ formatting on a Plotly trace.

    Hover shows: "Sales: ₹1.3L" or "Forecast: ₹73k".
    """
    formatted = [_fmt_rupee_short(float(v)) for v in values]
    return {
        "customdata": formatted,
        "hovertemplate": name + ": %{customdata}<extra></extra>",
    }


def _fmt_int_hover(values: list, name: str = "%{x|%b %d}") -> dict:
    """Build hovertemplate for integer values (covers, counts).

    Hover shows: "Covers: 72".
    """
    formatted = [f"{int(v)}" for v in values]
    return {
        "customdata": formatted,
        "hovertemplate": name + ": %{customdata}<extra></extra>",
    }


def _rupee_yaxis() -> dict:
    """Y-axis config with k/L shorthand labels."""
    return dict(
        tickprefix="₹",
        ticksuffix="",
        tickformat=",d",
    )


def _make_rupee_ticks(min_val: float, max_val: float) -> tuple:
    """Generate nice tick values and text for a rupee y-axis range.

    Returns (tickvals, ticktext) for Plotly.
    Examples:
      0-200k  → [0, 50000, 100000, 150000, 200000], ['₹0', '₹50k', ...]
      0-3L    → [0, 100000, 200000, 300000], ['₹0', '₹1L', ...]
    """
    range_val = max_val - min_val
    if range_val <= 0:
        return ([0], ["₹0"])

    # Choose step size
    if max_val <= 1_00_000:
        step = 10_000

        def fmt_fn(v: int) -> str:
            return f"₹{v / 1_000:.0f}k"

    elif max_val <= 5_00_000:
        step = 50_000

        def fmt_fn(v: int) -> str:
            return f"₹{v / 1_000:.0f}k"

    else:
        step = 1_00_000

        def fmt_fn(v: int) -> str:
            return f"₹{v / 1_00_000:.1f}L"

    start = 0
    tickvals = list(range(start, int(max_val) + 1, step))
    ticktext = [fmt_fn(v) for v in tickvals]
    return (tickvals, ticktext)


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


def _forecast_reliability_label(points: int) -> str:
    if points >= 21:
        return "High"
    if points >= 10:
        return "Medium"
    return "Low"


def render_forecast_command_center(
    df: pd.DataFrame,
    prior_df: pd.DataFrame,
    analysis_period: str,
    start_date: date,
    end_date: date,
    prior_start: date | None,
    prior_end: date | None,
    monthly_target: float,
    total_sales: float,
    avg_daily: float,
    total_covers: int,
    days_with_data: int,
    prior_total: float | None,
    prior_covers: int | None,
    prior_avg: float | None,
) -> None:
    """Render forecast-first executive block with actionable cards."""
    if df.empty:
        return

    dates = pd.to_datetime(df["date"])
    values = pd.to_numeric(df["net_total"], errors="coerce").fillna(0).tolist()
    selected_days = max(1, (end_date - start_date).days + 1)
    forecast_days = calculate_forecast_days(
        analysis_period,
        data_points=len(values),
        selected_range_days=selected_days,
    )
    forecast = linear_forecast(dates, values, forecast_days=forecast_days)
    forecast_total = total_sales + sum(f["value"] for f in (forecast or []))
    reliability = _forecast_reliability_label(len(values))

    action_cards = _build_action_cards(
        current_df=df,
        prior_df=prior_df,
        monthly_target=monthly_target,
        forecast_total=forecast_total if forecast else 0.0,
    )

    forecast_value = utils.format_rupee_short(forecast_total) if forecast else "N/A"
    target_gap = (
        utils.format_rupee_short(max(0.0, monthly_target - forecast_total))
        if monthly_target > 0 and forecast
        else "N/A"
    )
    cov_delta = None
    if prior_covers is not None and prior_covers > 0:
        cov_growth = utils.calculate_growth(total_covers, prior_covers)
        cov_delta = f"{cov_growth['percentage']:+.1f}%"

    apc = total_sales / total_covers if total_covers > 0 else 0.0
    prior_apc = (
        (prior_total / prior_covers)
        if prior_total is not None and prior_covers is not None and prior_covers > 0
        else None
    )
    apc_delta = None
    if prior_apc and prior_apc > 0:
        apc_delta = f"{((apc - prior_apc) / prior_apc) * 100:+.1f}%"

    metrics = [
        KpiMetric(
            label="Net Sales",
            value=utils.format_rupee_short(total_sales),
            delta=utils.format_delta(total_sales, prior_total) if prior_total else None,
        ),
        KpiMetric(
            label="Forecast",
            value=forecast_value,
            delta=f"Reliability: {reliability}",
        ),
        KpiMetric(
            label="Target Gap",
            value=target_gap,
            delta=(
                "On track"
                if monthly_target > 0 and forecast and forecast_total >= monthly_target
                else None
            ),
        ),
        KpiMetric(
            label="APC / Covers",
            value=f"{utils.format_currency(apc)} / {total_covers:,}",
            delta=f"APC {apc_delta or 'N/A'} | Covers {cov_delta or 'N/A'}",
        ),
    ]
    kpi_row(metrics)

    left_col, right_col = st.columns([2, 1])
    with left_col:
        fig = go.Figure()
        # Keep the hero chart to one story: observed points, smoothed trend, forecast.
        if len(values) >= 7:
            ma_values = moving_average(values, window=7)
            ma_series = pd.Series(ma_values)
            ma_mask = pd.notna(ma_series).values
            fig.add_trace(
                go.Scatter(
                    x=dates,
                    y=values,
                    mode="markers",
                    name="Daily sales",
                    marker=dict(
                        size=5,
                        color=_hex_to_rgba(ui_theme.BRAND_PRIMARY, 0.35),
                    ),
                    hovertemplate="₹%{y:,.0f}<br>%{x|%d %b}<extra></extra>",
                )
            )
            fig.add_trace(
                go.Scatter(
                    x=dates[ma_mask],
                    y=ma_series[ma_mask].tolist(),
                    mode="lines",
                    name="Trend",
                    line=dict(color=ui_theme.BRAND_PRIMARY, width=3),
                    hovertemplate="Trend: ₹%{y:,.0f}<br>%{x|%d %b}<extra></extra>",
                )
            )
        else:
            fig.add_trace(
                go.Scatter(
                    x=dates,
                    y=values,
                    mode="lines+markers",
                    name="Daily sales",
                    line=dict(color=ui_theme.BRAND_PRIMARY, width=2),
                    marker=dict(size=5),
                    hovertemplate="₹%{y:,.0f}<br>%{x|%d %b}<extra></extra>",
                )
            )
        if forecast:
            f_dates = [f["date"] for f in forecast]
            f_values = [f["value"] for f in forecast]
            fig.add_trace(
                go.Scatter(
                    x=f_dates,
                    y=f_values,
                    mode="lines",
                    name="Forecast",
                    line=dict(color=ui_theme.BRAND_WARN, width=3),
                    hovertemplate="Forecast: ₹%{y:,.0f}<br>%{x|%d %b}<extra></extra>",
                )
            )
            fig.add_vrect(
                x0=f_dates[0],
                x1=f_dates[-1],
                fillcolor=_hex_to_rgba(ui_theme.BRAND_WARN, 0.08),
                line_width=0,
                layer="below",
            )
        fig.update_layout(
            title="Forecast Trend",
            xaxis_title="Date",
            yaxis_title="Net Sales (₹)",
            hovermode="x unified",
            height=ui_theme.CHART_HEIGHT,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=-0.22,
                xanchor="center",
                x=0.5,
            ),
        )
        st.plotly_chart(fig, width="stretch")
        if prior_start and prior_end:
            st.caption(
                "Previous period is summarized in the KPI deltas: {} to {}.".format(
                    prior_start.strftime("%d %b %Y"),
                    prior_end.strftime("%d %b %Y"),
                )
            )

    with right_col:
        st.markdown("### Recommended Actions")
        for card in action_cards:
            body = (
                f"**{card['title']}**\n\n{card['reason']}\n\n"
                f"**Action:** {card['action']}\n\n{card['metric']}"
            )
            tone = card["severity"]
            if tone == "high":
                st.error(body)
            elif tone == "medium":
                st.warning(body)
            else:
                st.info(body)


def render_driver_analysis(
    df: pd.DataFrame,
    df_raw: pd.DataFrame,
    multi_analytics: bool,
) -> None:
    """Render focused traffic and ticket-size diagnostics."""
    if df.empty:
        st.caption("No driver data for this period.")
        return

    st.markdown("### Traffic & Ticket Drivers")
    st.caption("Use this layer to separate footfall movement from ticket-size movement.")

    if multi_analytics and not df_raw.empty:
        driver_df = (
            df_raw.groupby("date")[["covers", "net_total"]]
            .sum()
            .reset_index()
            .sort_values("date")
        )
    else:
        driver_df = df[["date", "covers", "net_total"]].copy().sort_values("date")

    driver_df["covers"] = pd.to_numeric(driver_df["covers"], errors="coerce").fillna(0)
    driver_df["net_total"] = pd.to_numeric(driver_df["net_total"], errors="coerce").fillna(0)
    driver_df["apc"] = driver_df.apply(
        lambda row: row["net_total"] / row["covers"] if row["covers"] > 0 else 0,
        axis=1,
    )

    covers_col, apc_col = st.columns(2)
    with covers_col:
        with st.container(border=True):
            st.markdown("#### Covers")
            fig_covers = go.Figure(
                go.Bar(
                    x=pd.to_datetime(driver_df["date"]),
                    y=driver_df["covers"],
                    name="Covers",
                    marker_color=ui_theme.BRAND_SUCCESS,
                    hovertemplate="%{y:,.0f} covers<br>%{x|%d %b}<extra></extra>",
                )
            )
            fig_covers.update_layout(
                xaxis_title="Date",
                yaxis_title="Covers",
                height=320,
                hovermode="x unified",
            )
            st.plotly_chart(fig_covers, width="stretch")

    with apc_col:
        with st.container(border=True):
            st.markdown("#### Average Per Cover")
            fig_apc = go.Figure(
                go.Scatter(
                    x=pd.to_datetime(driver_df["date"]),
                    y=driver_df["apc"],
                    mode="lines+markers",
                    name="APC",
                    line=dict(color=ui_theme.BRAND_PRIMARY, width=2),
                    marker=dict(size=4),
                    hovertemplate="₹%{y:,.0f} APC<br>%{x|%d %b}<extra></extra>",
                )
            )
            avg_apc = float(driver_df["apc"].mean()) if not driver_df.empty else 0.0
            if avg_apc > 0:
                fig_apc.add_hline(
                    y=avg_apc,
                    line_dash="dash",
                    line_color=ui_theme.CHART_BAR_MUTED,
                    annotation_text=f"Avg {utils.format_currency(avg_apc)}",
                )
            fig_apc.update_layout(
                xaxis_title="Date",
                yaxis_title="APC (₹)",
                height=320,
                hovermode="x unified",
            )
            st.plotly_chart(fig_apc, width="stretch")

    if st.toggle("Show driver data table", value=False, key="analytics_driver_table_toggle"):
        with st.container(border=True):
            st.caption("Daily driver table")
            table = driver_df.rename(
                columns={
                    "date": "Date",
                    "covers": "Covers",
                    "net_total": "Net Sales (₹)",
                    "apc": "APC (₹)",
                }
            )
            table["Net Sales (₹)"] = table["Net Sales (₹)"].apply(
                lambda val: utils.format_currency(float(val))
            )
            table["APC (₹)"] = table["APC (₹)"].apply(
                lambda val: utils.format_currency(float(val))
            )
            table["Covers"] = table["Covers"].apply(lambda val: f"{int(val):,}")
            st.dataframe(table, width="stretch", hide_index=True)


def render_mix_snapshot(
    report_loc_ids: list[int],
    start_str: str,
    end_str: str,
    df: pd.DataFrame,
    start_date: date,
) -> None:
    """Render concise category and weekday mix charts without default tables."""
    st.markdown("### Mix & Timing")
    st.caption("Use this layer to spot what is driving the period without digging through rows.")

    cat_col, weekday_col = st.columns(2)
    with cat_col:
        with st.container(border=True):
            st.markdown("#### Category Contribution")
            cat_data = database.get_category_sales_for_date_range(
                report_loc_ids,
                start_str,
                end_str,
            )
            if not cat_data:
                st.caption("No category data for this period.")
            else:
                cat_df = pd.DataFrame(cat_data).head(8).copy()
                total_cat = float(cat_df["amount"].sum())
                cat_df["share"] = (
                    cat_df["amount"] / total_cat * 100 if total_cat > 0 else 0
                )
                cat_df = cat_df.sort_values("amount", ascending=True)
                fig_cat = go.Figure(
                    go.Bar(
                        x=cat_df["amount"],
                        y=cat_df["category"],
                        orientation="h",
                        marker_color=ui_theme.BRAND_PRIMARY,
                        text=[f"{x:.1f}%" for x in cat_df["share"]],
                        textposition="auto",
                        hovertemplate=(
                            "%{y}<br>₹%{x:,.0f}<br>%{text} of top mix<extra></extra>"
                        ),
                    )
                )
                fig_cat.update_layout(
                    xaxis_title="Net Sales",
                    yaxis_title="",
                    height=360,
                    margin=dict(l=8, r=8, t=16, b=32),
                )
                fig_cat.update_xaxes(tickprefix="₹", tickformat=",")
                st.plotly_chart(fig_cat, width="stretch")

    with weekday_col:
        with st.container(border=True):
            st.markdown("#### Weekday Strength")
            if len(df) < 7:
                st.caption("Need at least 7 days of data for weekday strength.")
            else:
                wd_df = df[df["net_total"] > 0].copy()
                wd_df["weekday"] = wd_df["date"].apply(utils.get_weekday_name)
                wd_agg = (
                    wd_df.groupby("weekday")[["net_total", "covers"]]
                    .mean()
                    .reset_index()
                    .rename(columns={"net_total": "avg_sales", "covers": "avg_covers"})
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
                colors = [
                    ui_theme.BRAND_SUCCESS
                    if daily_tgt > 0 and val >= daily_tgt
                    else ui_theme.BRAND_WARN
                    if daily_tgt > 0 and val >= daily_tgt * 0.8
                    else ui_theme.CHART_BAR_MUTED
                    for val in wd_agg["avg_sales"]
                ]
                fig_wd = go.Figure(
                    go.Bar(
                        x=wd_agg["weekday"],
                        y=wd_agg["avg_sales"],
                        marker_color=colors,
                        text=[utils.format_rupee_short(v) for v in wd_agg["avg_sales"]],
                        textposition="outside",
                        hovertemplate=(
                            "%{x}<br>Avg sales: ₹%{y:,.0f}<extra></extra>"
                        ),
                    )
                )
                if daily_tgt > 0:
                    fig_wd.add_hline(
                        y=daily_tgt,
                        line_dash="dash",
                        line_color=ui_theme.CHART_BAR_MUTED,
                        annotation_text=f"Target {utils.format_rupee_short(daily_tgt)}",
                    )
                fig_wd.update_layout(
                    xaxis_title="",
                    yaxis_title="Avg Net Sales",
                    height=360,
                    margin=dict(l=8, r=8, t=16, b=32),
                )
                fig_wd.update_yaxes(tickprefix="₹", tickformat=",")
                st.plotly_chart(fig_wd, width="stretch")


def render_target_snapshot(
    report_loc_ids: list[int],
    start_date: date,
    df: pd.DataFrame,
) -> None:
    """Render a compact target snapshot without the legacy daily table."""
    st.markdown("### Target Pace")
    monthly_target = scope.sum_location_monthly_targets(report_loc_ids)
    if monthly_target <= 0 or df.empty:
        st.caption("No target data available for this period.")
        return

    target_df = df.copy().sort_values("date")
    target_df["net_total"] = pd.to_numeric(target_df["net_total"], errors="coerce").fillna(0)
    target_df["cumulative"] = target_df["net_total"].cumsum()
    days_in_month = utils.get_days_in_month(start_date.year, start_date.month)
    daily_target = monthly_target / days_in_month
    target_df["target_pace"] = [daily_target * (idx + 1) for idx in range(len(target_df))]
    actual_last = float(target_df["cumulative"].iloc[-1])
    target_last = float(target_df["target_pace"].iloc[-1])
    gap = actual_last - target_last

    status_col, chart_col = st.columns([1, 2])
    with status_col:
        with st.container(border=True):
            st.metric(
                "Actual vs Pace",
                utils.format_rupee_short(actual_last),
                utils.format_rupee_short(gap),
            )
            st.metric("Required Daily Pace", utils.format_rupee_short(daily_target))
            if gap >= 0:
                st.success("On pace for the selected target period.")
            else:
                st.warning("Behind target pace. Focus on high-confidence demand days.")

    with chart_col:
        with st.container(border=True):
            fig_target = go.Figure()
            fig_target.add_trace(
                go.Scatter(
                    x=pd.to_datetime(target_df["date"]),
                    y=target_df["cumulative"],
                    mode="lines+markers",
                    name="Actual",
                    fill="tozeroy",
                    fillcolor=_hex_to_rgba(ui_theme.BRAND_PRIMARY, 0.12),
                    line=dict(color=ui_theme.BRAND_PRIMARY, width=2),
                )
            )
            fig_target.add_trace(
                go.Scatter(
                    x=pd.to_datetime(target_df["date"]),
                    y=target_df["target_pace"],
                    mode="lines",
                    name="Target pace",
                    line=dict(color=ui_theme.CHART_BAR_MUTED, width=2, dash="dash"),
                )
            )
            fig_target.update_layout(
                xaxis_title="Date",
                yaxis_title="Cumulative Sales",
                height=360,
                hovermode="x unified",
                margin=dict(l=8, r=8, t=16, b=32),
            )
            fig_target.update_yaxes(tickprefix="₹", tickformat=",")
            st.plotly_chart(fig_target, width="stretch")


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
    st.markdown("### Period Summary")
    with st.container(border=True):
        show_projection = analysis_period in {"This Month", "MTD"}

        def _delta_str(current, prior):
            if prior is None or prior == 0:
                return None
            return utils.format_delta(current, prior)

        cov_delta = None
        if prior_covers is not None and prior_covers > 0:
            g = utils.calculate_growth(total_covers, prior_covers)
            sign = "+" if g["change"] >= 0 else ""
            cov_delta = (
                f"{sign}{int(g['change']):,} "
                f"({sign}{utils.format_percent(g['percentage'])})"
            )

        metrics = [
            KpiMetric(
                label="Total Sales",
                value=utils.format_rupee_short(total_sales),
                delta=_delta_str(total_sales, prior_total),
            ),
            KpiMetric(
                label="Total Covers",
                value=f"{total_covers:,}",
                delta=cov_delta,
            ),
            KpiMetric(
                label="Avg Daily Sales",
                value=utils.format_rupee_short(avg_daily),
                delta=_delta_str(avg_daily, prior_avg),
            ),
            KpiMetric(
                label="Days with Data",
                value=str(days_with_data),
            ),
        ]

        if show_projection:
            days_in_mo = utils.get_days_in_month(start_date.year, start_date.month)
            projected = utils.calculate_projected_sales(
                total_sales,
                days_with_data,
                days_in_mo,
            )
            metrics.append(
                KpiMetric(
                    label="Projected Month-End",
                    value=utils.format_rupee_short(projected),
                    help="Based on current run rate extrapolated to end of month.",
                )
            )

        kpi_row(metrics)


def render_sales_performance(
    df: pd.DataFrame,
    df_raw: pd.DataFrame,
    multi_analytics: bool,
    analysis_period: str = "",
) -> None:
    show_ma_and_forecast = _period_supports_trend_analysis(analysis_period, len(df))
    forecast = None

    st.markdown("### Sales Performance")
    with st.container(border=True):
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
                        ma_mask = pd.notna(ma_series).values
                        ma_valid = ma_series[ma_mask]
                        if not ma_valid.empty:
                            ma_color = outlet_colors.get(
                                outlet_name, ui_theme.CHART_MA_ACCENT
                            )
                            fig_line.add_trace(
                                go.Scatter(
                                    x=outlet_dates[ma_mask],
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
                    ma_mask = pd.notna(ma_series).values
                    ma_valid = ma_series[ma_mask]
                    if not ma_valid.empty:
                        fig_line.add_trace(
                            go.Scatter(
                                x=dates[ma_mask],
                                y=ma_valid.tolist(),
                                mode="lines",
                                name="7-day Avg",
                                line=dict(
                                    color=ui_theme.CHART_MA_ACCENT,
                                    width=2,
                                    dash="dash",
                                ),
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

                # Compute y-axis range for nice tick labels (only in single-outlet mode)
                all_vals = values[:]
                if forecast:
                    all_vals = values + [f["value"] for f in forecast]
                y_min, y_max = 0, max(all_vals) * 1.1 if all_vals else 200_000
                tickvals, ticktext = _make_rupee_ticks(y_min, y_max)

                fig_line.update_layout(
                    xaxis_title="Date",
                    yaxis_title="Net Sales (₹)",
                    hovermode="x unified",
                    height=ui_theme.CHART_HEIGHT,
                    xaxis=dict(tickformat="%b %d"),
                    yaxis=dict(
                        tickprefix="₹",
                        tickvals=tickvals,
                        ticktext=ticktext,
                    ),
                )

            if multi_analytics and not df_raw.empty:
                fig_line.update_layout(
                    xaxis_title="Date",
                    yaxis_title="Net Sales (₹)",
                    hovermode="x unified",
                    height=ui_theme.CHART_HEIGHT,
                    xaxis=dict(tickformat="%b %d"),
                )
            st.plotly_chart(fig_line, width="stretch")

            # Screen reader summary
            if not multi_analytics and values:
                _chart_summary(
                    "Daily sales range from {} to {} across {} days.".format(
                        utils.format_rupee_short(min(values)),
                        utils.format_rupee_short(max(values)),
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
            st.plotly_chart(fig_covers, width="stretch")

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
            st.plotly_chart(fig_apc, width="stretch")
            _chart_summary(
                "Average per cover is {} across {} days with data.".format(
                    utils.format_currency(avg_apc),
                    len(apc_df),
                )
            )
        else:
            st.caption("No APC data for this period.")

        # ── Sales Performance drill-down table ───────────────────
        with st.container(border=True):
            st.caption("Sales performance table")
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
            st.dataframe(_sales_tbl, width="stretch", hide_index=True)


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
                        "pct": other_amount / total_cat * 100 if total_cat > 0 else 0,
                    }
                ]
            )
            chart_df = pd.concat([large_cats, other_row], ignore_index=True)
        else:
            chart_df = large_cats.copy()

        fig_cat = go.Figure(
            go.Treemap(
                labels=chart_df["category"].tolist(),
                values=chart_df["amount"].tolist(),
                parents=[""] * len(chart_df),
                marker=dict(
                    colors=[
                        ui_theme.CHART_COLORWAY[i % len(ui_theme.CHART_COLORWAY)]
                        for i in range(len(chart_df))
                    ]
                ),
                textinfo="label+percent entry",
            )
        )
        fig_cat.update_layout(
            title=f"Category revenue mix (Total: {utils.format_rupee_short(total_cat)})",
            height=400,
        )

        st.plotly_chart(fig_cat, width="stretch")

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
        with st.container(border=True):
            st.caption("Category data")
            st.dataframe(_cat_table, width="stretch", hide_index=True)
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
        if monthly_tgt > 0 and len(report_loc_ids) == 1:
            recent = database.get_recent_summaries(report_loc_ids[0], weeks=8)
            weekday_mix = utils.compute_weekday_mix(recent)
            day_targets = utils.compute_day_targets(monthly_tgt, weekday_mix)
            daily_tgt = sum(day_targets.values()) / len(day_targets)
        else:
            days_in_mo = utils.get_days_in_month(start_date.year, start_date.month)
            daily_tgt = monthly_tgt / days_in_mo if monthly_tgt > 0 else 0

        if wd_agg.empty:
            st.caption("No positive-sales days available for weekday analysis.")
            return

        # Best/worst day identification for conditional coloring
        best_idx = wd_agg["avg_sales"].idxmax()
        worst_idx = wd_agg["avg_sales"].idxmin()
        wd_colors = []
        for i in range(len(wd_agg)):
            if i == best_idx:
                wd_colors.append(ui_theme.CHART_POSITIVE)
            elif i == worst_idx:
                wd_colors.append(ui_theme.CHART_NEGATIVE)
            else:
                wd_colors.append(ui_theme.CHART_NEUTRAL)

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
                annotation_text=f"Daily target {utils.format_rupee_short(daily_tgt)}",
                annotation_position="top right",
            )

        # Best/worst day annotations
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
        st.plotly_chart(fig_wd, width="stretch")
        _chart_summary(
            "Best day is {} (avg {}) and worst is {} (avg {}).".format(
                best_day,
                utils.format_rupee_short(best_val),
                worst_day,
                utils.format_rupee_short(worst_val),
            )
        )

        # Weekday drill-down table
        with st.container(border=True):
            st.caption("Weekday data")
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
                width="stretch",
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

        weekday_mix: dict = {}
        day_targets: dict = {}
        if len(report_loc_ids) == 1:
            recent = database.get_recent_summaries(report_loc_ids[0], weeks=8)
            weekday_mix = utils.compute_weekday_mix(recent)
            day_targets = utils.compute_day_targets(monthly_target, weekday_mix)

        fig_target = make_subplots(
            rows=1,
            cols=2,
            subplot_titles=["Daily Achievement %", "Cumulative vs Target"],
            specs=[[{"type": "bar"}, {"type": "scatter"}]],
        )

        target_df = df.copy()
        if day_targets:
            target_df["day_target"] = target_df["date"].apply(
                lambda d: utils.get_target_for_date(day_targets, str(d))
            )
            target_df["achievement"] = target_df.apply(
                lambda r: (
                    r["net_total"] / r["day_target"] * 100 if r["day_target"] > 0 else 0
                ),
                axis=1,
            )
        else:
            daily_target = monthly_target / days_in_month
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
        st.plotly_chart(fig_target, width="stretch")

        # On-track / Behind badge
        if actual_last >= target_last:
            st.success(
                "✅ **On track** — "
                f"{utils.format_rupee_short(actual_last - target_last)} "
                "ahead of target pace"
            )
        else:
            st.error(
                "⚠️ **Behind by "
                f"{utils.format_rupee_short(target_last - actual_last)}" 
                "** — below target pace"
            )

        _chart_summary(
            "Cumulative sales are {} vs target pace of {}.".format(
                utils.format_rupee_short(actual_last),
                utils.format_rupee_short(target_last),
            )
        )

        # Target achievement drill-down table
        with st.container(border=True):
            st.caption("Target achievement data")
            _cols_needed = {"target", "pct_target"}
            _has_target_cols = (
                multi_analytics
                and not df_raw.empty
                and _cols_needed.issubset(df_raw.columns)
            )

            if _has_target_cols:
                _tgt_tbl = df_raw[
                    ["date", "Outlet", "net_total", "target", "pct_target"]
                ].copy()
                _tgt_tbl["pct_target"] = _tgt_tbl["pct_target"].apply(
                    lambda x: f"{float(x or 0):.2f}%"
                )
            else:
                _target_col = (
                    "day_target" if "day_target" in target_df.columns else None
                )
                _cols = ["date", "net_total"]
                if _target_col:
                    _cols.extend([_target_col, "achievement"])
                else:
                    _cols.append("achievement")
                _tgt_tbl = target_df[_cols].copy()
                _tgt_tbl["achievement"] = _tgt_tbl["achievement"].apply(
                    lambda x: f"{float(x or 0):.2f}%"
                )
                if _target_col:
                    _tgt_tbl = _tgt_tbl.rename(columns={_target_col: "target"})
                _tgt_tbl = _tgt_tbl.rename(columns={"achievement": "pct_target"})

            _rename_cols = {
                "date": "Date",
                "net_total": "Net Sales (₹)",
                "pct_target": "Achievement",
            }
            if "target" in _tgt_tbl.columns:
                _rename_cols["target"] = "Target (₹)"
            _tgt_tbl = _tgt_tbl.rename(columns=_rename_cols)
            _tgt_tbl["Net Sales (₹)"] = _tgt_tbl["Net Sales (₹)"].apply(
                lambda x: utils.format_currency(float(x))
            )
            if "Target (₹)" in _tgt_tbl.columns:
                _tgt_tbl["Target (₹)"] = _tgt_tbl["Target (₹)"].apply(
                    lambda x: utils.format_currency(float(x))
                )
            st.dataframe(_tgt_tbl, width="stretch", hide_index=True)

        st.markdown("### Daily Data")
        dv = build_daily_view_table(df, df_raw, multi_analytics, numeric=True)

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
                "Achievement %": "{:.2f}%",
            },
            na_rep="",
        )
        # Bold the total row
        _total_row_idx_multi = len(dv_display) - 1
        styler = styler.set_properties(
            subset=pd.IndexSlice[_total_row_idx_multi, :],
            **{"font-weight": "bold"},
        )
        st.dataframe(styler, width="stretch", hide_index=True)
    else:
        daily_view = build_daily_view_table(
            df, pd.DataFrame(), multi_analytics=False, numeric=True
        )

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
                "Achievement %": "{:.2f}%",
            },
            na_rep="",
        )
        _total_row_idx = len(dv_display) - 1
        styler = styler.set_properties(
            subset=pd.IndexSlice[_total_row_idx, :],
            **{"font-weight": "bold"},
        )
        st.dataframe(styler, width="stretch", hide_index=True)


def render_payment_reconciliation(
    report_loc_ids: list[int],
    start_str: str,
    end_str: str,
) -> None:
    """Render per-provider payment breakdown for ops team reconciliation."""
    from io import BytesIO

    import database_analytics

    st.markdown("### Payment Reconciliation")
    st.caption(
        "Per-provider breakdown for reconciling against Paytm / PhonePe / GPay settlement "
        "statements. Live data shows raw Payment Type labels; "
        "local mode shows the 5-bucket summary."
    )

    data = database_analytics.get_payment_provider_breakdown(
        report_loc_ids, start_str, end_str
    )

    if not data:
        st.caption("No payment data for this period.")
        return

    recon_df = pd.DataFrame(data)
    total_gross = float(recon_df["gross_amount"].sum())
    recon_df["% of Total"] = recon_df["gross_amount"].apply(
        lambda x: f"{x / total_gross * 100:.1f}%" if total_gross > 0 else "0%"
    )

    has_txn_count = recon_df["txn_count"].notna().any()

    display_df = recon_df.copy()
    display_df["Gross Amount (₹)"] = display_df["gross_amount"].apply(
        lambda x: utils.format_currency(float(x))
    )
    display_df = display_df.rename(columns={"provider": "Provider"})

    cols_to_show = ["Provider", "Gross Amount (₹)", "% of Total"]
    if has_txn_count:
        display_df = display_df.rename(columns={"txn_count": "Bills"})
        display_df["Bills"] = display_df["Bills"].fillna(0).astype(int)
        cols_to_show = ["Provider", "Bills", "Gross Amount (₹)", "% of Total"]

    st.dataframe(display_df[cols_to_show], width="stretch", hide_index=True)

    recon_metrics = [
        KpiMetric(
            label="Total Gross (period)",
            value=utils.format_currency(total_gross),
        ),
    ]
    if has_txn_count:
        recon_metrics.append(
            KpiMetric(
                label="Total Bills",
                value=f"{int(recon_df['txn_count'].sum()):,}",
            )
        )
    kpi_row(recon_metrics)

    export_df = recon_df[["provider", "txn_count", "gross_amount", "% of Total"]].copy()
    export_df = export_df.rename(
        columns={
            "provider": "Provider",
            "txn_count": "Bill Count",
            "gross_amount": "Gross Amount",
        }
    )
    c1, c2 = st.columns(2)
    with c1:
        csv_bytes = export_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="Download CSV",
            data=csv_bytes,
            file_name=f"payment_recon_{start_str}_{end_str}.csv",
            mime="text/csv",
            key="recon_csv_btn",
        )
    with c2:
        excel_buf = BytesIO()
        with pd.ExcelWriter(excel_buf, engine="openpyxl") as writer:
            export_df.to_excel(writer, index=False, sheet_name="Payment Reconciliation")
        excel_buf.seek(0)
        st.download_button(
            label="Download Excel",
            data=excel_buf.getvalue(),
            file_name=f"payment_recon_{start_str}_{end_str}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="recon_excel_btn",
        )
