"""Chart builder functions for analytics dashboard."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

import ui_theme
import utils
from tabs.forecasting import moving_average, linear_forecast


def _hex_to_rgba(hex_color: str, alpha: float = 0.2) -> str:
    """Convert hex color to rgba string with given alpha.

    Args:
        hex_color: Color in hex format (e.g., "#1F5FA8")
        alpha: Alpha transparency (0.0-1.0)

    Returns:
        RGBA color string
    """
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


def _period_supports_trend_analysis(period: str, data_points: int) -> bool:
    """Return True if period is long enough for MA and forecast."""
    _long_periods = {"Last 7 Days", "Last 30 Days", "Last Month", "Custom"}
    if period in _long_periods:
        return data_points >= 3
    return False


def build_sales_trend_chart(
    df: pd.DataFrame,
    df_raw: pd.DataFrame,
    multi_analytics: bool,
    analysis_period: str = "",
) -> go.Figure:
    """Build Daily Sales Trend chart with optional 7-day moving average.

    Args:
        df: Aggregated daily summary (single location or all combined)
        df_raw: Raw daily data with outlet information (for multi-outlet)
        multi_analytics: True if viewing multiple outlets
        analysis_period: Period name for determining if MA should show

    Returns:
        Plotly Figure with sales trend and optional MA line
    """
    show_ma = _period_supports_trend_analysis(analysis_period, len(df))

    # Multi-outlet: aggregate by date
    if multi_analytics and not df_raw.empty:
        df_agg = df_raw.groupby("date")["net_total"].sum().reset_index()
        dates = pd.to_datetime(df_agg["date"])
        values = df_agg["net_total"].tolist()
    else:
        dates = pd.to_datetime(df["date"])
        values = df["net_total"].tolist()

    fig = go.Figure()

    # Actual sales area
    fig.add_trace(
        go.Scatter(
            x=dates,
            y=values,
            mode="lines+markers",
            name="Daily Sales",
            fill="tozeroy",
            fillcolor=_hex_to_rgba(ui_theme.BRAND_PRIMARY, 0.15),
            line=dict(color=ui_theme.BRAND_PRIMARY, width=2),
            marker=dict(size=4),
        )
    )

    # 7-day moving average (only for longer periods)
    if show_ma and len(values) >= 7:
        ma_values = moving_average(values, window=7)
        ma_series = pd.Series(ma_values)
        ma_valid = ma_series[pd.notna(ma_series)]
        if not ma_valid.empty:
            fig.add_trace(
                go.Scatter(
                    x=dates[pd.notna(ma_series)],
                    y=ma_valid.tolist(),
                    mode="lines",
                    name="7-day Avg",
                    line=dict(color=ui_theme.BRAND_WARN, width=2, dash="dot"),
                    opacity=0.8,
                )
            )

    fig.update_layout(
        xaxis_title="Date",
        yaxis_title="Net Sales (₹)",
        hovermode="x unified",
        height=ui_theme.CHART_HEIGHT,
    )

    return fig


def build_apc_chart(df: pd.DataFrame) -> go.Figure | None:
    """Build APC Trend chart with y-axis starting at 0.

    Args:
        df: Daily summary data with 'apc' column

    Returns:
        Plotly Figure or None if no APC data
    """
    apc_df = df[df["apc"] > 0].copy() if "apc" in df.columns else pd.DataFrame()
    if apc_df.empty:
        return None

    dates = pd.to_datetime(apc_df["date"])
    apc_values = apc_df["apc"].tolist()

    fig = px.line(
        apc_df,
        x="date",
        y="apc",
        markers=True,
        title="APC over time",
    )
    fig.update_traces(line_color=ui_theme.BRAND_PRIMARY)

    # Add average line
    avg_apc = float(apc_df["apc"].mean())
    fig.add_hline(
        y=avg_apc,
        line_dash="dash",
        line_color="gray",
        annotation_text=f"Avg {utils.format_currency(avg_apc)}",
        annotation_position="top right",
    )

    # Set Y-axis to start at 0 with 10% buffer at top
    max_apc = max(apc_values)
    fig.update_yaxes(range=[0, max_apc * 1.1])

    fig.update_layout(
        xaxis_title="Date",
        yaxis_title="APC (₹)",
        hovermode="x unified",
        height=ui_theme.CHART_HEIGHT,
    )

    return fig


def build_weekday_chart(df: pd.DataFrame, daily_target: float) -> go.Figure:
    """Build Weekday Analysis chart with conditional bar coloring.

    Best day (highest avg sales): Green
    Worst day (lowest avg sales): Red
    Other days: Neutral gray

    Args:
        df: Daily summary data
        daily_target: Daily sales target for reference line

    Returns:
        Plotly Figure with weekday bars
    """
    wd_df = df[df["net_total"] > 0].copy()
    wd_df["weekday"] = wd_df["date"].apply(utils.get_weekday_name)

    wd_agg = (
        wd_df.groupby("weekday")["net_total"]
        .mean()
        .reset_index()
        .rename(columns={"net_total": "avg_sales"})
    )

    # Sort by day of week
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

    # Determine best and worst days
    best_idx = wd_agg["avg_sales"].idxmax()
    worst_idx = wd_agg["avg_sales"].idxmin()
    best_day = wd_agg.loc[best_idx, "weekday"]
    worst_day = wd_agg.loc[worst_idx, "weekday"]

    # Color mapping: green for best, red for worst, gray for others
    colors = [
        ui_theme.BRAND_SUCCESS
        if day == best_day
        else ui_theme.BRAND_ERROR
        if day == worst_day
        else "#94A3B8"  # neutral gray
        for day in wd_agg["weekday"]
    ]

    fig = go.Figure(
        data=[
            go.Bar(
                x=wd_agg["weekday"],
                y=wd_agg["avg_sales"],
                marker_color=colors,
                name="Avg Sales",
            )
        ]
    )

    # Add target line
    if daily_target > 0:
        fig.add_hline(
            y=daily_target,
            line_dash="dash",
            line_color="gray",
            annotation_text=f"Daily target {utils.format_currency(daily_target)}",
            annotation_position="top right",
        )

    # Add best/worst annotations
    fig.add_annotation(
        x=best_day,
        y=wd_agg.loc[best_idx, "avg_sales"],
        text=f"Best: {best_day}",
        showarrow=True,
        arrowhead=2,
        bgcolor=ui_theme.BRAND_SUCCESS,
        font_color="white",
    )
    fig.add_annotation(
        x=worst_day,
        y=wd_agg.loc[worst_idx, "avg_sales"],
        text=f"Worst: {worst_day}",
        showarrow=True,
        arrowhead=2,
        bgcolor=ui_theme.BRAND_ERROR,
        font_color="white",
    )

    fig.update_layout(
        title="Average net sales by day of week",
        xaxis_title="",
        yaxis_title="Avg Net Sales (₹)",
        height=ui_theme.CHART_HEIGHT,
        showlegend=False,
    )

    return fig


def build_category_chart(
    cat_df: pd.DataFrame, min_percent_threshold: float = 2.0
) -> go.Figure | None:
    """Build Category Mix donut chart with 'Other' grouping for small categories.

    Categories below min_percent_threshold are grouped into 'Other' slice.

    Args:
        cat_df: DataFrame with 'category' and 'amount' columns
        min_percent_threshold: Minimum percentage to display as separate slice

    Returns:
        Plotly Figure with donut chart or None if empty
    """
    if cat_df.empty:
        return None

    cat_df = cat_df.copy()
    total_cat = float(cat_df["amount"].sum())
    cat_df["pct"] = cat_df["amount"] / total_cat * 100

    # Group small categories into "Other"
    small_cats = cat_df[cat_df["pct"] < min_percent_threshold]
    major_cats = cat_df[cat_df["pct"] >= min_percent_threshold].copy()

    if not small_cats.empty:
        other_amount = small_cats["amount"].sum()
        other_row = pd.DataFrame(
            {
                "category": ["Other"],
                "amount": [other_amount],
                "pct": [other_amount / total_cat * 100],
            }
        )
        cat_df_chart = pd.concat([major_cats, other_row], ignore_index=True)
    else:
        cat_df_chart = major_cats

    fig = px.treemap(
        cat_df_chart,
        names="category",
        values="amount",
        title=f"Category revenue mix (Total: {utils.format_currency(total_cat)})",
        color="category",
        color_discrete_sequence=ui_theme.CHART_COLORWAY,
    )
    fig.update_traces(textinfo="label+percent entry")
    fig.update_layout(height=ui_theme.CHART_HEIGHT)

    return fig
