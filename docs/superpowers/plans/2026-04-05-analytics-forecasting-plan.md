# Analytics Tab Forecasting & Chart Consolidation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce Analytics tab from 10+ charts to 6 focused charts + 1 table, and add linear-regression forecasting to Sales and Covers trends with gradient styling.

**Architecture:** Create a new `tabs/forecasting.py` module for pure forecasting/moving-average helpers. Rewrite `tabs/analytics_sections.py` to render only the kept charts with forecast overlays. Update `tabs/analytics_tab.py` to remove deleted section calls and pass new data.

**Tech Stack:** Streamlit, Plotly, pandas, numpy (already a pandas dependency), existing database.py queries

---

## File Structure

| File | Change | Purpose |
|------|--------|---------|
| `tabs/forecasting.py` | Create | Pure functions: linear regression forecast, moving average, forecast date generation |
| `tabs/analytics_sections.py` | Rewrite | 6 section renderers (down from 10+ charts) with forecast overlays |
| `tabs/analytics_tab.py` | Modify | Remove calls to deleted sections, pass `prior_df` to sections that need it |
| `tests/test_forecasting.py` | Create | Tests for forecasting pure functions |

---

### Task 1: Create Forecasting Helpers

**Files:**
- Create: `tabs/forecasting.py`
- Test: `tests/test_forecasting.py`

- [ ] **Step 1: Write tests for forecasting helpers**

```python
"""Tests for pure forecasting helper logic."""

import numpy as np
import pandas as pd

from tabs.forecasting import (
    linear_forecast,
    moving_average,
    generate_forecast_dates,
)


class TestLinearForecast:
    def test_returns_empty_when_fewer_than_7_points(self):
        dates = pd.to_datetime(["2026-04-01", "2026-04-02", "2026-04-03"])
        values = [100, 200, 150]
        result = linear_forecast(dates, values, forecast_days=2)
        assert result is None

    def test_returns_forecast_with_correct_length(self):
        dates = pd.to_datetime([f"2026-04-{d:02d}" for d in range(1, 16)])
        values = [float(100 + i * 5) for i in range(15)]
        result = linear_forecast(dates, values, forecast_days=5)
        assert result is not None
        assert len(result) == 5

    def test_forecast_has_expected_keys(self):
        dates = pd.to_datetime([f"2026-04-{d:02d}" for d in range(1, 16)])
        values = [float(100 + i * 5) for i in range(15)]
        result = linear_forecast(dates, values, forecast_days=3)
        assert result is not None
        for entry in result:
            assert "date" in entry
            assert "value" in entry
            assert "upper" in entry
            assert "lower" in entry

    def test_upward_trend_produces_increasing_forecast(self):
        dates = pd.to_datetime([f"2026-04-{d:02d}" for d in range(1, 16)])
        values = [float(100 + i * 10) for i in range(15)]
        result = linear_forecast(dates, values, forecast_days=5)
        assert result is not None
        assert result[0]["value"] < result[-1]["value"]

    def test_flat_values_produce_flat_forecast(self):
        dates = pd.to_datetime([f"2026-04-{d:02d}" for d in range(1, 16)])
        values = [100.0] * 15
        result = linear_forecast(dates, values, forecast_days=3)
        assert result is not None
        # All forecast values should be approximately 100
        for entry in result:
            assert abs(entry["value"] - 100.0) < 1.0

    def test_std_dev_band_widens_with_distance(self):
        """Uncertainty should increase the further out we forecast."""
        dates = pd.to_datetime([f"2026-04-{d:02d}" for d in range(1, 16)])
        values = [100.0 + float(i) * 5 for i in range(15)]
        result = linear_forecast(dates, values, forecast_days=7)
        assert result is not None
        # Last forecast entry should have a wider band than the first
        first_band = result[0]["upper"] - result[0]["lower"]
        last_band = result[-1]["upper"] - result[-1]["lower"]
        assert last_band > first_band


class TestMovingAverage:
    def test_returns_same_length_as_input(self):
        values = [10, 20, 30, 40, 50, 60, 70, 80]
        result = moving_average(values, window=3)
        assert len(result) == len(values)

    def test_first_values_are_nan_when_window_exceeds_available(self):
        values = [10, 20, 30]
        result = moving_average(values, window=5)
        # First entries before we have enough data should be NaN
        import math
        assert math.isnan(result[0])
        assert math.isnan(result[1])

    def test_computes_correct_3_window_average(self):
        values = [10.0, 20.0, 30.0, 40.0]
        result = moving_average(values, window=3)
        import math
        assert math.isnan(result[0])
        assert math.isnan(result[1])
        assert result[2] == 20.0  # (10+20+30)/3
        assert result[3] == 30.0  # (20+30+40)/3

    def test_window_of_1_returns_original(self):
        values = [10.0, 20.0, 30.0]
        result = moving_average(values, window=1)
        assert result == values


class TestGenerateForecastDates:
    def test_generates_correct_number_of_dates(self):
        last_date = pd.Timestamp("2026-04-15")
        result = generate_forecast_dates(last_date, forecast_days=5)
        assert len(result) == 5

    def test_dates_are_consecutive(self):
        last_date = pd.Timestamp("2026-04-15")
        result = generate_forecast_dates(last_date, forecast_days=3)
        assert result[0] == pd.Timestamp("2026-04-16")
        assert result[1] == pd.Timestamp("2026-04-17")
        assert result[2] == pd.Timestamp("2026-04-18")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_forecasting.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'tabs.forecasting'"

- [ ] **Step 3: Write forecasting module**

```python
"""Forecasting helpers for analytics charts.

Pure functions: linear regression forecast, moving average, forecast date generation.
No Streamlit or database dependencies.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd


def linear_forecast(
    dates: pd.Series,
    values: List[float],
    forecast_days: int = 5,
) -> Optional[List[Dict[str, Any]]]:
    """Linear regression forecast with ±1 std dev confidence band.

    Returns None if fewer than 7 data points (not enough for reliable forecast).
    Each entry: {"date": Timestamp, "value": float, "upper": float, "lower": float}
    """
    if len(values) < 7:
        return None

    x = np.arange(len(values), dtype=float)
    y = np.array(values, dtype=float)

    coeffs = np.polyfit(x, y, 1)
    slope, intercept = coeffs[0], coeffs[1]

    residuals = y - (slope * x + intercept)
    std_err = float(np.std(residuals))

    last_date = pd.Timestamp(dates.iloc[-1])
    forecast_dates = generate_forecast_dates(last_date, forecast_days)

    result: List[Dict[str, Any]] = []
    for i, fdate in enumerate(forecast_dates):
        future_x = len(values) + i
        value = slope * future_x + intercept
        band = std_err * (1 + i * 0.15)
        result.append({
            "date": fdate,
            "value": float(value),
            "upper": float(value + band),
            "lower": float(max(0, value - band)),
        })

    return result


def moving_average(
    values: List[float],
    window: int = 7,
) -> List[float]:
    """Compute simple moving average. Returns same length as input.

    Leading entries (before enough data for the window) are NaN.
    """
    if window <= 0:
        return list(values)
    if window == 1:
        return list(values)

    result: List[float] = []
    for i in range(len(values)):
        if i < window - 1:
            result.append(float("nan"))
        else:
            window_vals = values[i - window + 1 : i + 1]
            result.append(sum(window_vals) / len(window_vals))
    return result


def generate_forecast_dates(
    last_date: pd.Timestamp,
    forecast_days: int,
) -> List[pd.Timestamp]:
    """Generate consecutive dates starting the day after last_date."""
    return [last_date + timedelta(days=i + 1) for i in range(forecast_days)]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_forecasting.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add tabs/forecasting.py tests/test_forecasting.py
git commit -m "feat(analytics): add forecasting helpers with tests"
```

---

### Task 2: Rewrite Analytics Sections — Sales Performance (with Forecast)

**Files:**
- Modify: `tabs/analytics_sections.py` — rewrite `render_sales_performance`

- [ ] **Step 1: Rewrite `render_sales_performance` with forecast overlays**

Replace the entire `render_sales_performance` function in `tabs/analytics_sections.py` with:

```python
def render_sales_performance(
    df: pd.DataFrame,
    df_raw: pd.DataFrame,
    multi_analytics: bool,
    prior_df: pd.DataFrame = pd.DataFrame(),
) -> None:
    """Render Sales Performance section: sales trend, covers trend, APC."""
    from tabs.forecasting import linear_forecast, moving_average, generate_forecast_dates

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
                fig_line.update_layout(
                    xaxis_title="Date",
                    yaxis_title="Net Sales (₹)",
                    hovermode="x unified",
                    height=ui_theme.CHART_HEIGHT,
                )
                st.plotly_chart(fig_line, use_container_width=True)
            else:
                dates = pd.to_datetime(df["date"])
                values = df["net_total"].tolist()
                ma_values = moving_average(values, window=7)

                fig_line = go.Figure()

                # Actual sales line
                fig_line.add_trace(go.Scatter(
                    x=dates,
                    y=values,
                    mode="lines+markers",
                    name="Daily Sales",
                    line=dict(color=ui_theme.BRAND_PRIMARY, width=2),
                    marker=dict(size=5),
                ))

                # 7-day moving average
                ma_dates = dates[pd.notna(pd.Series(ma_values))]
                ma_vals = [v for v in ma_values if not pd.isna(v)]
                if len(ma_vals) > 0:
                    fig_line.add_trace(go.Scatter(
                        x=ma_dates,
                        y=ma_vals,
                        mode="lines",
                        name="7-day MA",
                        line=dict(color=ui_theme.BRAND_PRIMARY, width=1.5, dash="dot"),
                        opacity=0.6,
                    ))

                # Forecast
                forecast_days = max(len(values) // 2, 3)
                forecast = linear_forecast(dates, values, forecast_days=forecast_days)
                if forecast:
                    f_dates = [f["date"] for f in forecast]
                    f_values = [f["value"] for f in forecast]
                    f_upper = [f["upper"] for f in forecast]
                    f_lower = [f["lower"] for f in forecast]

                    # Forecast line
                    fig_line.add_trace(go.Scatter(
                        x=f_dates,
                        y=f_values,
                        mode="lines",
                        name="Forecast",
                        line=dict(color=ui_theme.BRAND_PRIMARY, width=2, dash="dash"),
                        opacity=0.6,
                    ))

                    # Forecast band
                    fig_line.add_trace(go.Scatter(
                        x=f_dates + f_dates[::-1],
                        y=f_upper + f_lower[::-1],
                        fill="toself",
                        fillcolor=f"rgba(31,95,168,0.15)",
                        line=dict(color="transparent"),
                        name="Forecast Range",
                        showlegend=False,
                        hoverinfo="skip",
                    ))

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
                fig_bar.update_layout(
                    xaxis_title="Date",
                    yaxis_title="Covers",
                    height=ui_theme.CHART_HEIGHT,
                )
                st.plotly_chart(fig_bar, use_container_width=True)
            else:
                dates = pd.to_datetime(df["date"])
                covers = df["covers"].tolist()

                fig_bar = go.Figure()

                # Actual covers bars
                fig_bar.add_trace(go.Bar(
                    x=dates,
                    y=covers,
                    name="Covers",
                    marker_color=ui_theme.BRAND_SUCCESS,
                ))

                # Forecast bars
                forecast_days = max(len(covers) // 2, 3)
                forecast = linear_forecast(dates, covers, forecast_days=forecast_days)
                if forecast:
                    f_dates = [f["date"] for f in forecast]
                    f_values = [max(0, f["value"]) for f in forecast]
                    fig_bar.add_trace(go.Bar(
                        x=f_dates,
                        y=f_values,
                        name="Forecast",
                        marker_color=ui_theme.BRAND_SUCCESS,
                        opacity=0.4,
                    ))

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
```

- [ ] **Step 2: Run Streamlit to verify**

Run: `streamlit run app.py` → Analytics tab → Verify Sales Performance section renders with forecast on sales trend and covers trend.

- [ ] **Step 3: Commit**

```bash
git add tabs/analytics_sections.py
git commit -m "feat(analytics): rewrite Sales Performance with forecast overlays"
```

---

### Task 3: Rewrite Analytics Sections — Category Mix, Weekday, Target

**Files:**
- Modify: `tabs/analytics_sections.py` — rewrite `render_revenue_breakdown` and `render_target_and_daily`

- [ ] **Step 1: Rewrite `render_revenue_breakdown` — keep only Category Mix donut and Weekday Analysis**

Replace the entire `render_revenue_breakdown` function with:

```python
def render_revenue_breakdown(
    report_loc_ids: list[int],
    start_str: str,
    end_str: str,
    df: pd.DataFrame,
    start_date: date,
) -> None:
    """Render Category Mix (donut only) and Weekday Analysis sections."""
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
            "Monday", "Tuesday", "Wednesday", "Thursday",
            "Friday", "Saturday", "Sunday",
        ]
        wd_agg["weekday"] = pd.Categorical(
            wd_agg["weekday"], categories=day_order, ordered=True
        )
        wd_agg = wd_agg.sort_values("weekday")
        monthly_tgt = scope.sum_location_monthly_targets(report_loc_ids)
        days_in_mo = utils.get_days_in_month(start_date.year, start_date.month)
        daily_tgt = (
            monthly_tgt / days_in_mo if monthly_tgt > 0 else 0
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

        # Best/worst day annotations
        if not wd_agg.empty:
            best_idx = wd_agg["avg_sales"].idxmax()
            worst_idx = wd_agg["avg_sales"].idxmin()
            best_day = wd_agg.loc[best_idx, "weekday"]
            best_val = wd_agg.loc[best_idx, "avg_sales"]
            worst_day = wd_agg.loc[worst_idx, "weekday"]
            worst_val = wd_agg.loc[worst_idx, "avg_sales"]
            fig_wd.add_annotation(
                x=best_day, y=best_val,
                text=f"Best: {best_day}",
                showarrow=True, arrowhead=2,
                bgcolor=ui_theme.BRAND_SUCCESS,
                font_color="white",
            )
            fig_wd.add_annotation(
                x=worst_day, y=worst_val,
                text=f"Worst: {worst_day}",
                showarrow=True, arrowhead=2,
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
```

- [ ] **Step 2: Rewrite `render_target_and_daily` — add projected month-end and on-track badge**

Replace the entire `render_target_and_daily` function with:

```python
def render_target_and_daily(
    report_loc_ids: list[int],
    start_date: date,
    df: pd.DataFrame,
    df_raw: pd.DataFrame,
    multi_analytics: bool,
) -> None:
    """Render Target Achievement with projection and Daily Data table."""
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
            row=1, col=1,
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
                fill="tozeroy",
                fillcolor=(
                    "rgba(63,167,163,0.2)"
                    if df_sorted["cumulative"].iloc[-1] >= target_line[-1]
                    else "rgba(239,68,68,0.2)"
                ),
            ),
            row=1, col=2,
        )
        fig_target.add_trace(
            go.Scatter(
                x=df_sorted["date"],
                y=target_line,
                mode="lines",
                name="Target",
                line=dict(dash="dash", color="gray"),
            ),
            row=1, col=2,
        )

        # Projected month-end extension
        last_date = pd.Timestamp(df_sorted["date"].iloc[-1])
        month_end = pd.Timestamp(start_date.replace(day=days_in_month))
        if last_date < month_end and len(df_sorted) >= 3:
            from tabs.forecasting import linear_forecast
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
                        row=1, col=2,
                    )

        fig_target.update_layout(height=ui_theme.CHART_HEIGHT, showlegend=True)
        st.plotly_chart(fig_target, use_container_width=True)

        # On-track / Behind badge
        actual_cum = df_sorted["cumulative"].iloc[-1]
        expected_cum = target_line[-1]
        if actual_cum >= expected_cum:
            st.success(f"✅ **On track** — ₹{actual_cum - expected_cum:,.0f} ahead of target pace")
        else:
            st.error(f"⚠️ **Behind by {utils.format_currency(expected_cum - actual_cum)}** — below target pace")

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
```

- [ ] **Step 3: Run Streamlit to verify**

Run: `streamlit run app.py` → Analytics tab → Verify Category Mix (donut only), Weekday Analysis (with annotations), Target Achievement (with projection + badge).

- [ ] **Step 4: Commit**

```bash
git add tabs/analytics_sections.py
git commit -m "feat(analytics): rewrite Category Mix, Weekday, Target sections"
```

---

### Task 4: Update Analytics Tab — Remove Deleted Sections, Wire New Data

**Files:**
- Modify: `tabs/analytics_tab.py`

- [ ] **Step 1: Update imports and render calls**

Replace the `render` function body starting from the section render calls (around line 116). The current code calls:
```python
render_overview(...)
render_sales_performance(df, df_raw, multi_analytics)
render_revenue_breakdown(ctx.report_loc_ids, start_str, end_str, df, start_date)
render_target_and_daily(ctx.report_loc_ids, start_date, df, df_raw, multi_analytics)
```

Change to:

```python
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
        )
        render_revenue_breakdown(
            ctx.report_loc_ids,
            start_str,
            end_str,
            df,
            start_date,
        )
        render_target_and_daily(
            ctx.report_loc_ids,
            start_date,
            df,
            df_raw,
            multi_analytics,
        )
```

The only change is adding `prior_df=prior_df` to `render_sales_performance`. The deleted sections (payment mode, top items, meal period) are removed by the section rewrites in Tasks 2-3.

- [ ] **Step 2: Run Streamlit to verify full tab**

Run: `streamlit run app.py` → Analytics tab → Verify all 6 sections render correctly with no errors.

- [ ] **Step 3: Run existing tests**

Run: `pytest tests/test_analytics_logic.py -v`
Expected: All PASS (no changes to analytics_logic.py)

- [ ] **Step 4: Commit**

```bash
git add tabs/analytics_tab.py
git commit -m "feat(analytics): wire prior_df to Sales Performance section"
```

---

### Task 5: Full Verification & Edge Cases

**Files:**
- Test: Manual verification

- [ ] **Step 1: Test all period options**

Run: `streamlit run app.py` → Analytics tab
- [ ] This Week
- [ ] Last Week
- [ ] Last 7 Days
- [ ] This Month
- [ ] Last Month
- [ ] Last 30 Days
- [ ] Custom (short range <7 days — should show "Need at least 7 days" caption)
- [ ] Custom (long range >7 days — should show forecast)

- [ ] **Step 2: Test edge cases**
- [ ] Period with zero sales days: charts render gracefully
- [ ] Period with exactly 7 days: forecast appears (minimum threshold)
- [ ] Multi-outlet view: charts aggregate correctly
- [ ] No category data: shows "No category data" caption
- [ ] No APC data: shows "No APC data" caption

- [ ] **Step 3: Run all tests**

Run: `pytest tests/ -v`
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
git commit -m "test(analytics): verify all periods and edge cases"
```

---

## Summary

| Task | Changes |
|------|---------|
| 1 | Create `tabs/forecasting.py` + tests |
| 2 | Rewrite `render_sales_performance` with forecast overlays |
| 3 | Rewrite `render_revenue_breakdown` (category donut + weekday) and `render_target_and_daily` (projection + badge) |
| 4 | Update `analytics_tab.py` to wire new data |
| 5 | Full verification & edge case testing |

**Plan complete.**
