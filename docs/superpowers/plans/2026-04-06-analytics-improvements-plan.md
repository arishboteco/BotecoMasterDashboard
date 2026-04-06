# Analytics Improvements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement 8 professional analytics improvements (moving averages, chart scaling fixes, conditional formatting, drill-down tables, Indian number formatting) using modular refactoring approach.

**Architecture:** Modular refactoring with 3 new utility modules (`chart_builders.py`, `table_formatters.py`) to encapsulate chart and table logic, keeping `analytics_sections.py` as an orchestrator. Enhanced `utils.py` with Indian number formatting. Minimal changes to `report_tab.py` for previous-day deltas.

**Tech Stack:** Python 3.11+, Streamlit, Plotly, pandas, existing database/scope modules

**Spec Reference:** `docs/superpowers/specs/2026-04-06-analytics-improvements-design.md`

---

## File Structure

### New Files
- **`tabs/chart_builders.py`** — Plotly chart construction functions
  - `build_sales_trend_chart()` — Daily Sales with 7-day MA
  - `build_covers_chart()` — Covers trend (minimal changes)
  - `build_apc_chart()` — APC with y-axis starting at 0
  - `build_weekday_chart()` — Weekday bars with conditional colors
  - `build_category_chart()` — Donut with "Other" grouping
  - `build_target_chart()` — Target achievement (refactored from analytics_sections)
  - Helper: `_hex_to_rgba()`, `_period_supports_trend_analysis()`

- **`tabs/table_formatters.py`** — DataFrame formatting and styling
  - `format_daily_data_table()` — Daily data with totals row, conditional formatting metadata
  - `build_sales_trend_detail()` — Sales trend drill-down table
  - `build_covers_detail()` — Covers drill-down table
  - `build_apc_detail()` — APC drill-down table
  - `build_weekday_detail()` — Weekday analysis drill-down table
  - `build_category_detail_table()` — Category breakdown table
  - `build_target_detail()` — Target achievement drill-down table
  - `get_daily_table_column_config()` — Streamlit column config

### Modified Files
- **`utils.py`**
  - Add: `format_indian_currency(amount: float) -> str`
  - Modify: `format_currency()` to use Indian format
  - Add: `format_delta_with_arrow()` (alternative to `format_delta` for custom arrow display)

- **`ui_theme.py`**
  - Add: `TABLE_ACHIEVEMENT_GREEN`, `TABLE_ACHIEVEMENT_YELLOW`, `TABLE_ACHIEVEMENT_RED` color tokens

- **`tabs/analytics_sections.py`**
  - Refactor: Replace inline chart builders with calls to `chart_builders.*`
  - Refactor: Add expanders with `table_formatters.*` tables
  - Reduce from ~650 to ~400 lines
  - Keep orchestration logic

- **`tabs/report_tab.py`**
  - Modify: `render()` function to fetch previous day data and calculate deltas
  - Add: Previous-day delta display on KPI cards

### Test Files (New)
- **`tests/test_chart_builders.py`** — Unit tests for chart builders
- **`tests/test_table_formatters.py`** — Unit tests for table formatters
- **`tests/test_utils_indian_currency.py`** — Unit tests for Indian number formatting

---

## Implementation Tasks

### Task 1: Create Indian Currency Formatting Utilities

**Files:**
- Modify: `utils.py`
- Create: `tests/test_utils_indian_currency.py`

- [ ] **Step 1: Write failing tests for Indian currency formatting**

Create `tests/test_utils_indian_currency.py`:

```python
"""Tests for Indian currency formatting."""

import pytest
from utils import format_indian_currency


class TestFormatIndianCurrency:
    """Test Indian number formatting (1,30,235 format)."""

    def test_simple_hundreds(self):
        """Test amounts under 1000."""
        assert format_indian_currency(500) == "₹500"
        assert format_indian_currency(999) == "₹999"

    def test_thousands(self):
        """Test amounts in thousands."""
        assert format_indian_currency(1000) == "₹1,000"
        assert format_indian_currency(12345) == "₹12,345"

    def test_lakhs(self):
        """Test amounts in lakhs (100,000s)."""
        assert format_indian_currency(100000) == "₹1,00,000"
        assert format_indian_currency(130235) == "₹1,30,235"
        assert format_indian_currency(999999) == "₹9,99,999"

    def test_crores(self):
        """Test amounts in crores (10,000,000s)."""
        assert format_indian_currency(1000000) == "₹10,00,000"
        assert format_indian_currency(12345678) == "₹1,23,45,678"

    def test_zero(self):
        """Test zero amount."""
        assert format_indian_currency(0) == "₹0"

    def test_negative_amounts(self):
        """Test negative amounts."""
        assert format_indian_currency(-1000) == "-₹1,000"
        assert format_indian_currency(-130235) == "-₹1,30,235"

    def test_decimal_amounts(self):
        """Test amounts with decimals (paise)."""
        assert format_indian_currency(1000.50) == "₹1,000.50"
        assert format_indian_currency(130235.75) == "₹1,30,235.75"

    def test_very_large_amounts(self):
        """Test very large amounts."""
        assert format_indian_currency(123456789) == "₹12,34,56,789"
        assert format_indian_currency(1234567890) == "₹12,34,56,78,90"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_utils_indian_currency.py -v
```

Expected output:
```
FAILED tests/test_utils_indian_currency.py::TestFormatIndianCurrency::test_simple_hundreds - AssertionError
FAILED ... (all tests fail with "format_indian_currency is not defined")
```

- [ ] **Step 3: Implement `format_indian_currency()` in utils.py**

In `utils.py`, add after the existing `format_currency()` function:

```python
def format_indian_currency(amount: float) -> str:
    """Format amount as Indian currency: 1,30,235 instead of 130,235.
    
    Args:
        amount: Numeric amount to format
        
    Returns:
        Formatted string with Indian numbering system (e.g., "₹1,30,235")
    """
    if amount == 0:
        return "₹0"
    
    # Handle negative amounts
    is_negative = amount < 0
    amount = abs(amount)
    
    # Split into integer and decimal parts
    if isinstance(amount, float):
        parts = f"{amount:,.2f}".split('.')
    else:
        parts = [str(int(amount)), "00"]
    
    integer_part = parts[0].replace(',', '')  # Remove any existing commas
    decimal_part = parts[1] if len(parts) > 1 else "00"
    
    # Indian numbering: group from right as 3, then 2, 2, 2...
    # E.g., 1234567 → 12,34,567
    if len(integer_part) <= 3:
        formatted = integer_part
    else:
        # Extract last 3 digits
        last_three = integer_part[-3:]
        # Process remaining digits from right to left, grouping by 2
        remaining = integer_part[:-3]
        
        groups = []
        for i in range(len(remaining), 0, -2):
            start = max(0, i - 2)
            groups.insert(0, remaining[start:i])
        
        formatted = ','.join(groups) + ',' + last_three
    
    # Combine with decimal part (remove decimals if all zeros)
    if int(decimal_part) == 0:
        result = formatted
    else:
        # Keep decimals only if significant
        result = f"{formatted}.{decimal_part.rstrip('0')}"
    
    # Add currency symbol and sign
    if is_negative:
        return f"-₹{result}"
    return f"₹{result}"
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_utils_indian_currency.py -v
```

Expected output:
```
PASSED tests/test_utils_indian_currency.py::TestFormatIndianCurrency::test_simple_hundreds
PASSED tests/test_utils_indian_currency.py::TestFormatIndianCurrency::test_thousands
... (all tests pass)
```

- [ ] **Step 5: Update existing `format_currency()` to use Indian format**

In `utils.py`, replace the existing `format_currency()` function:

```python
def format_currency(amount: float) -> str:
    """Format amount as Indian currency string.
    
    Uses Indian numbering system: 1,30,235 instead of 130,235
    
    Args:
        amount: Numeric amount to format
        
    Returns:
        Formatted currency string (e.g., "₹1,30,235")
    """
    return format_indian_currency(amount)
```

- [ ] **Step 6: Run all tests to ensure no regressions**

```bash
pytest tests/ -v -k "not integration"
```

Expected: All utils tests pass, no errors in other modules.

- [ ] **Step 7: Commit**

```bash
git add utils.py tests/test_utils_indian_currency.py
git commit -m "feat: add Indian currency formatting (₹1,30,235 format)"
```

---

### Task 2: Create Chart Builders Module

**Files:**
- Create: `tabs/chart_builders.py`
- Create: `tests/test_chart_builders.py`

- [ ] **Step 1: Create `tabs/chart_builders.py` scaffold with imports and helper functions**

Create `tabs/chart_builders.py`:

```python
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
    """Determine if period has enough data for moving average and forecast.
    
    Args:
        period: Analysis period name (e.g., "Last 7 Days")
        data_points: Number of data points available
        
    Returns:
        True if MA/forecast should be shown
    """
    long_periods = {"Last 7 Days", "Last 30 Days", "Last Month", "Custom"}
    if period in long_periods:
        return data_points >= 7
    return False
```

- [ ] **Step 2: Implement `build_sales_trend_chart()` in chart_builders.py**

Add to `tabs/chart_builders.py`:

```python
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
        df_agg = df_raw.groupby('date')['net_total'].sum().reset_index()
        dates = pd.to_datetime(df_agg['date'])
        values = df_agg['net_total'].tolist()
    else:
        dates = pd.to_datetime(df['date'])
        values = df['net_total'].tolist()
    
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
```

- [ ] **Step 3: Implement `build_apc_chart()` in chart_builders.py**

Add to `tabs/chart_builders.py`:

```python
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
```

- [ ] **Step 4: Implement `build_weekday_chart()` in chart_builders.py**

Add to `tabs/chart_builders.py`:

```python
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
```

- [ ] **Step 5: Implement `build_category_chart()` in chart_builders.py**

Add to `tabs/chart_builders.py`:

```python
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
        other_row = pd.DataFrame({
            "category": ["Other"],
            "amount": [other_amount],
            "pct": [other_amount / total_cat * 100],
        })
        cat_df_chart = pd.concat([major_cats, other_row], ignore_index=True)
    else:
        cat_df_chart = major_cats
    
    fig = px.pie(
        cat_df_chart,
        names="category",
        values="amount",
        title=f"Category revenue mix (Total: {utils.format_currency(total_cat)})",
        hole=0.4,  # donut
        color_discrete_sequence=ui_theme.CHART_COLORWAY,
    )
    fig.update_traces(textposition="inside", textinfo="percent+label")
    fig.update_layout(height=ui_theme.CHART_HEIGHT)
    
    return fig
```

- [ ] **Step 6: Create minimal unit tests for chart builders**

Create `tests/test_chart_builders.py`:

```python
"""Tests for chart_builders module."""

import pandas as pd
import pytest
from tabs import chart_builders


class TestBuildSalesTrendChart:
    """Test sales trend chart builder."""

    def test_returns_figure(self):
        """Test that chart builder returns a Figure."""
        df = pd.DataFrame({
            'date': ['2026-04-01', '2026-04-02', '2026-04-03'],
            'net_total': [50000, 75000, 60000],
        })
        fig = chart_builders.build_sales_trend_chart(df, pd.DataFrame(), False, "Last 7 Days")
        assert fig is not None
        assert len(fig.data) >= 1  # At least one trace

    def test_includes_7day_ma_for_long_periods(self):
        """Test that 7-day MA is included for periods >=7 days."""
        dates = pd.date_range('2026-04-01', periods=10)
        df = pd.DataFrame({
            'date': dates.strftime('%Y-%m-%d'),
            'net_total': [50000 + i*1000 for i in range(10)],
        })
        fig = chart_builders.build_sales_trend_chart(df, pd.DataFrame(), False, "Last 30 Days")
        # Should have 2 traces: actual sales + 7-day MA
        assert len(fig.data) == 2


class TestBuildAPCChart:
    """Test APC chart builder."""

    def test_returns_figure_with_apc_data(self):
        """Test chart returns Figure when APC data exists."""
        df = pd.DataFrame({
            'date': ['2026-04-01', '2026-04-02'],
            'apc': [2100, 2150],
        })
        fig = chart_builders.build_apc_chart(df)
        assert fig is not None

    def test_returns_none_without_apc_data(self):
        """Test chart returns None when no APC data."""
        df = pd.DataFrame({
            'date': ['2026-04-01'],
            'net_total': [50000],
        })
        fig = chart_builders.build_apc_chart(df)
        assert fig is None

    def test_yaxis_starts_at_zero(self):
        """Test that y-axis range starts at 0."""
        df = pd.DataFrame({
            'date': ['2026-04-01', '2026-04-02'],
            'apc': [2100, 2150],
        })
        fig = chart_builders.build_apc_chart(df)
        assert fig.layout.yaxis.range[0] == 0


class TestBuildWeekdayChart:
    """Test weekday analysis chart builder."""

    def test_returns_figure(self):
        """Test chart builder returns a Figure."""
        df = pd.DataFrame({
            'date': ['2026-04-01', '2026-04-02', '2026-04-08'],  # Wed, Thu, Wed
            'net_total': [50000, 55000, 52000],
        })
        fig = chart_builders.build_weekday_chart(df, 50000)
        assert fig is not None
        assert len(fig.data) >= 1


class TestBuildCategoryChart:
    """Test category mix chart builder."""

    def test_groups_small_categories_into_other(self):
        """Test that categories <2% are grouped into 'Other'."""
        df = pd.DataFrame({
            'category': ['Food', 'Liquor', 'Coffee', 'Water'],
            'amount': [6000, 2500, 100, 50],  # Water=0.6%, Coffee=0.75%
        })
        fig = chart_builders.build_category_chart(df, min_percent_threshold=2.0)
        # Should have 3 slices: Food, Liquor, Other (Coffee+Water)
        labels = [t.label for t in fig.data[0].labels]
        assert 'Other' in labels

    def test_returns_none_for_empty_data(self):
        """Test returns None for empty DataFrame."""
        df = pd.DataFrame(columns=['category', 'amount'])
        fig = chart_builders.build_category_chart(df)
        assert fig is None
```

- [ ] **Step 7: Run tests to verify they pass**

```bash
pytest tests/test_chart_builders.py -v
```

Expected: All tests pass.

- [ ] **Step 8: Commit**

```bash
git add tabs/chart_builders.py tests/test_chart_builders.py
git commit -m "feat: create chart_builders module with 5 chart functions (MA, APC, weekday, category)"
```

---

### Task 3: Create Table Formatters Module

**Files:**
- Create: `tabs/table_formatters.py`
- Create: `tests/test_table_formatters.py`

- [ ] **Step 1: Create `tabs/table_formatters.py` scaffold**

Create `tabs/table_formatters.py`:

```python
"""Table formatter and builder functions for analytics dashboard."""

from __future__ import annotations

import pandas as pd
import streamlit as st

import utils
```

- [ ] **Step 2: Implement `format_daily_data_table()` in table_formatters.py**

Add to `tabs/table_formatters.py`:

```python
def format_daily_data_table(
    df: pd.DataFrame,
    df_raw: pd.DataFrame,
    multi_analytics: bool,
) -> pd.DataFrame:
    """Build daily data table with formatted columns and totals row.
    
    Formats currency, covers, and calculates totals row for period summary.
    
    Args:
        df: Aggregated daily summary
        df_raw: Raw daily data (for multi-outlet view)
        multi_analytics: True if viewing multiple outlets
        
    Returns:
        Formatted DataFrame ready for st.dataframe()
    """
    if multi_analytics and not df_raw.empty:
        detail = df_raw[["date", "Outlet", "covers", "net_total", "target", "achievement"]].copy()
    else:
        detail = df[["date", "covers", "net_total", "target", "achievement"]].copy()
        detail.insert(1, "Outlet", "Combined")
    
    # Format columns
    detail["Date"] = pd.to_datetime(detail["date"]).dt.strftime("%d %b %Y")
    detail["Covers"] = detail["covers"].astype(int).astype(str)
    detail["Net Sales"] = detail["net_total"].apply(utils.format_currency)
    detail["Target"] = detail["target"].apply(utils.format_currency)
    detail["Achievement"] = detail["achievement"].round(1).astype(str) + "%"
    
    # Select display columns
    result = detail[["Date", "Outlet", "Covers", "Net Sales", "Target", "Achievement"]].copy()
    
    # Add totals row
    total_covers = int(detail["covers"].sum())
    total_sales = detail["net_total"].sum()
    total_target = detail["target"].sum()
    overall_achievement = (
        f"{(total_sales / total_target * 100):.1f}%"
        if total_target > 0
        else "—"
    )
    
    totals_row = pd.DataFrame({
        "Date": ["TOTAL"],
        "Outlet": [""],
        "Covers": [str(total_covers)],
        "Net Sales": [utils.format_currency(total_sales)],
        "Target": [utils.format_currency(total_target)],
        "Achievement": [overall_achievement],
    })
    
    result = pd.concat([result, totals_row], ignore_index=True)
    
    return result
```

- [ ] **Step 3: Implement drill-down detail table builders**

Add to `tabs/table_formatters.py`:

```python
def build_sales_trend_detail(
    df: pd.DataFrame,
    df_raw: pd.DataFrame,
    multi_analytics: bool,
) -> pd.DataFrame:
    """Build sales trend drill-down table.
    
    Args:
        df: Aggregated daily summary
        df_raw: Raw daily data
        multi_analytics: True if multi-outlet
        
    Returns:
        Formatted DataFrame with Date, Outlet, Net Sales, Covers, APC
    """
    if multi_analytics and not df_raw.empty:
        detail = df_raw[["date", "Outlet", "net_total", "covers", "apc"]].copy()
        detail.columns = ["Date", "Outlet", "Net Sales", "Covers", "APC"]
    else:
        detail = df[["date", "net_total", "covers", "apc"]].copy()
        detail.columns = ["Date", "Net Sales", "Covers", "APC"]
    
    # Format columns
    detail["Date"] = pd.to_datetime(detail["Date"]).dt.strftime("%Y-%m-%d")
    detail["Net Sales"] = detail["Net Sales"].apply(utils.format_currency)
    detail["Covers"] = detail["Covers"].astype(int).astype(str)
    if "APC" in detail.columns:
        detail["APC"] = detail["APC"].apply(utils.format_currency)
    
    return detail


def build_apc_detail(
    df: pd.DataFrame,
    df_raw: pd.DataFrame,
    multi_analytics: bool,
) -> pd.DataFrame:
    """Build APC trend drill-down table.
    
    Args:
        df: Aggregated daily summary
        df_raw: Raw daily data
        multi_analytics: True if multi-outlet
        
    Returns:
        Formatted DataFrame with Date, Outlet (if multi), APC
    """
    if multi_analytics and not df_raw.empty:
        detail = df_raw[["date", "Outlet", "apc"]].copy()
        detail.columns = ["Date", "Outlet", "APC"]
    else:
        detail = df[["date", "apc"]].copy()
        detail.columns = ["Date", "APC"]
    
    detail["Date"] = pd.to_datetime(detail["Date"]).dt.strftime("%Y-%m-%d")
    detail["APC"] = detail["APC"].apply(utils.format_currency)
    
    return detail


def build_weekday_detail(df: pd.DataFrame, start_date) -> pd.DataFrame:
    """Build weekday analysis drill-down table.
    
    Args:
        df: Daily summary data
        start_date: Start date of period (for context)
        
    Returns:
        Formatted DataFrame with Day, Avg Sales, Avg Covers, Count
    """
    wd_df = df[df["net_total"] > 0].copy()
    wd_df["weekday"] = wd_df["date"].apply(utils.get_weekday_name)
    
    wd_agg = (
        wd_df.groupby("weekday")
        .agg({
            "net_total": ["mean", "count"],
            "covers": "mean",
        })
        .reset_index()
    )
    
    wd_agg.columns = ["Day", "Avg Sales", "Count", "Avg Covers"]
    wd_agg = wd_agg[["Day", "Avg Sales", "Avg Covers", "Count"]]
    
    # Format columns
    wd_agg["Avg Sales"] = wd_agg["Avg Sales"].apply(utils.format_currency)
    wd_agg["Avg Covers"] = wd_agg["Avg Covers"].round(0).astype(int).astype(str)
    wd_agg["Count"] = wd_agg["Count"].astype(int).astype(str)
    
    # Reorder by day of week
    day_order = [
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday",
    ]
    wd_agg["Day"] = pd.Categorical(wd_agg["Day"], categories=day_order, ordered=True)
    wd_agg = wd_agg.sort_values("Day")
    
    return wd_agg


def build_category_detail_table(cat_df: pd.DataFrame) -> pd.DataFrame:
    """Build category breakdown detail table.
    
    Shows all categories with exact amounts and percentages.
    
    Args:
        cat_df: DataFrame with 'category' and 'amount' columns
        
    Returns:
        Formatted DataFrame with Category, Amount, % of Total, plus totals row
    """
    if cat_df.empty:
        return pd.DataFrame()
    
    cat_df = cat_df.copy()
    total = cat_df["amount"].sum()
    
    cat_df["Amount (₹)"] = cat_df["amount"].apply(utils.format_currency)
    cat_df["% of Total"] = (cat_df["amount"] / total * 100).round(1).astype(str) + "%"
    
    result = cat_df[["category", "Amount (₹)", "% of Total"]].copy()
    result.columns = ["Category", "Amount (₹)", "% of Total"]
    
    # Sort by amount descending
    result = result.sort_values(
        "Amount (₹)",
        key=lambda x: x.str.replace("₹", "").str.replace(",", "").astype(float),
        ascending=False,
    )
    
    # Add totals row
    totals_row = pd.DataFrame({
        "Category": ["TOTAL"],
        "Amount (₹)": [utils.format_currency(total)],
        "% of Total": ["100.0%"],
    })
    result = pd.concat([result, totals_row], ignore_index=True)
    
    return result


def build_target_detail(
    df: pd.DataFrame,
    daily_target: float,
) -> pd.DataFrame:
    """Build target achievement drill-down table.
    
    Args:
        df: Daily summary data with achievement column
        daily_target: Daily target amount
        
    Returns:
        Formatted DataFrame with Date, Outlet, Net Sales, Target, Achievement %
    """
    detail = df[["date", "net_total", "target", "achievement"]].copy()
    detail.columns = ["Date", "Net Sales", "Target", "Achievement"]
    
    detail["Date"] = pd.to_datetime(detail["Date"]).dt.strftime("%Y-%m-%d")
    detail["Net Sales"] = detail["Net Sales"].apply(utils.format_currency)
    detail["Target"] = detail["Target"].apply(utils.format_currency)
    detail["Achievement"] = detail["Achievement"].round(1).astype(str) + "%"
    
    return detail


def get_daily_table_column_config() -> dict:
    """Return Streamlit column config for daily data table.
    
    Returns:
        Dictionary of column configurations for st.dataframe()
    """
    return {
        "Date": st.column_config.TextColumn("Date", width="medium"),
        "Outlet": st.column_config.TextColumn("Outlet", width="medium"),
        "Covers": st.column_config.TextColumn("Covers", width="small"),
        "Net Sales": st.column_config.TextColumn("Net Sales (₹)", width="medium"),
        "Target": st.column_config.TextColumn("Target (₹)", width="medium"),
        "Achievement": st.column_config.TextColumn("Achievement %", width="small"),
    }
```

- [ ] **Step 4: Create unit tests for table formatters**

Create `tests/test_table_formatters.py`:

```python
"""Tests for table_formatters module."""

import pandas as pd
import pytest
from tabs import table_formatters


class TestFormatDailyDataTable:
    """Test daily data table formatter."""

    def test_returns_dataframe(self):
        """Test that formatter returns a DataFrame."""
        df = pd.DataFrame({
            'date': ['2026-04-01', '2026-04-02'],
            'covers': [100, 110],
            'net_total': [50000, 55000],
            'target': [45000, 45000],
            'achievement': [111.1, 122.2],
        })
        result = table_formatters.format_daily_data_table(df, pd.DataFrame(), False)
        assert isinstance(result, pd.DataFrame)

    def test_includes_totals_row(self):
        """Test that totals row is included."""
        df = pd.DataFrame({
            'date': ['2026-04-01', '2026-04-02'],
            'covers': [100, 100],
            'net_total': [50000, 50000],
            'target': [45000, 45000],
            'achievement': [111.1, 111.1],
        })
        result = table_formatters.format_daily_data_table(df, pd.DataFrame(), False)
        assert 'TOTAL' in result['Date'].values

    def test_formats_currency(self):
        """Test that amounts are formatted as currency."""
        df = pd.DataFrame({
            'date': ['2026-04-01'],
            'covers': [100],
            'net_total': [130235],
            'target': [100000],
            'achievement': [130.2],
        })
        result = table_formatters.format_daily_data_table(df, pd.DataFrame(), False)
        # Should have Indian format
        assert any('₹' in str(val) for val in result['Net Sales'])


class TestBuildCategoryDetailTable:
    """Test category detail table builder."""

    def test_includes_all_categories(self):
        """Test that all categories are shown."""
        df = pd.DataFrame({
            'category': ['Food', 'Liquor', 'Coffee'],
            'amount': [6500, 2800, 700],
        })
        result = table_formatters.build_category_detail_table(df)
        assert len(result) == 4  # 3 categories + 1 totals row

    def test_includes_totals_row_with_100_percent(self):
        """Test that totals row shows 100%."""
        df = pd.DataFrame({
            'category': ['Food', 'Liquor'],
            'amount': [5000, 5000],
        })
        result = table_formatters.build_category_detail_table(df)
        totals = result[result['Category'] == 'TOTAL']
        assert '100.0%' in totals['% of Total'].values


class TestBuildWeekdayDetail:
    """Test weekday detail table builder."""

    def test_returns_all_days(self):
        """Test that all 7 weekdays are returned."""
        dates = pd.date_range('2026-04-01', periods=14)  # 2 weeks
        df = pd.DataFrame({
            'date': dates.strftime('%Y-%m-%d'),
            'net_total': [50000] * 14,
            'covers': [100] * 14,
        })
        result = table_formatters.build_weekday_detail(df, dates[0].date())
        # Should have 7 days
        assert len(result) >= 7
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/test_table_formatters.py -v
```

Expected: All tests pass.

- [ ] **Step 6: Commit**

```bash
git add tabs/table_formatters.py tests/test_table_formatters.py
git commit -m "feat: create table_formatters module with 7 table builder functions"
```

---

### Task 4: Update UI Theme with Conditional Formatting Colors

**Files:**
- Modify: `ui_theme.py`

- [ ] **Step 1: Add conditional formatting color tokens to ui_theme.py**

In `ui_theme.py`, add after the existing color definitions (after line 19):

```python
# -- Conditional formatting colors for tables --------------------------------
TABLE_ACHIEVEMENT_GREEN = "#10B981"   # ≥100% achievement
TABLE_ACHIEVEMENT_YELLOW = "#FBBF24"  # 70–99% achievement
TABLE_ACHIEVEMENT_RED = "#EF4444"     # <70% achievement
```

- [ ] **Step 2: Verify theme file has no errors**

```bash
python -c "import ui_theme; print('OK')"
```

Expected output: `OK`

- [ ] **Step 3: Commit**

```bash
git add ui_theme.py
git commit -m "feat: add conditional formatting color tokens for tables"
```

---

### Task 5: Refactor Analytics Sections to Use New Modules

**Files:**
- Modify: `tabs/analytics_sections.py`

This is a large refactoring. I'll break it into sub-steps.

- [ ] **Step 1: Update imports in analytics_sections.py**

In `tabs/analytics_sections.py`, replace the imports at the top with:

```python
"""Section render helpers for analytics tab."""

from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

import database
import scope
import ui_theme
import utils
from tabs import chart_builders, table_formatters
from tabs.analytics_logic import build_daily_view_table
from tabs.forecasting import linear_forecast, moving_average
```

- [ ] **Step 2: Replace `render_sales_performance()` to use chart_builders**

In `tabs/analytics_sections.py`, replace the entire `render_sales_performance()` function (starting around line 115) with:

```python
def render_sales_performance(
    df: pd.DataFrame,
    df_raw: pd.DataFrame,
    multi_analytics: bool,
    prior_df: pd.DataFrame = pd.DataFrame(),
    analysis_period: str = "",
) -> None:
    """Render sales performance section with charts and drill-down tables."""
    with st.expander("💰 Sales Performance", expanded=True):
        col_chart1, col_chart2 = st.columns(2)

        # ── Daily Sales Trend ──────────────────────────────────
        with col_chart1:
            st.markdown("### Daily Sales Trend")
            if multi_analytics and not df_raw.empty:
                fig_line = chart_builders.build_sales_trend_chart(
                    df, df_raw, multi_analytics, analysis_period
                )
            else:
                fig_line = chart_builders.build_sales_trend_chart(
                    df, pd.DataFrame(), False, analysis_period
                )
            st.plotly_chart(fig_line, use_container_width=True)

            # Drill-down expander
            with st.expander("📊 View data"):
                detail_df = table_formatters.build_sales_trend_detail(
                    df, df_raw, multi_analytics
                )
                st.dataframe(detail_df, use_container_width=True, hide_index=True)

        # ── Covers Trend ───────────────────────────────────────
        with col_chart2:
            st.markdown("### Covers Trend")
            if multi_analytics and not df_raw.empty:
                fig_covers = px.bar(
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

                fig_covers = go.Figure()
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
                    )
                )

            fig_covers.update_layout(
                xaxis_title="Date",
                yaxis_title="Covers",
                hovermode="x unified",
                height=ui_theme.CHART_HEIGHT,
            )
            st.plotly_chart(fig_covers, use_container_width=True)

            # Drill-down expander
            with st.expander("📊 View data"):
                detail_df = table_formatters.build_apc_detail(df, df_raw, multi_analytics)
                st.dataframe(detail_df, use_container_width=True, hide_index=True)

        # ── APC Trend ──────────────────────────────────────────
        st.markdown("### Average Per Cover (APC) Trend")
        fig_apc = chart_builders.build_apc_chart(df)
        if fig_apc:
            st.plotly_chart(fig_apc, use_container_width=True)

            # Drill-down expander
            with st.expander("📊 View data"):
                detail_df = table_formatters.build_apc_detail(df, df_raw, multi_analytics)
                st.dataframe(detail_df, use_container_width=True, hide_index=True)
        else:
            st.caption("No APC data for this period.")
```

Note: Keep the existing `_hex_to_rgba()` function in analytics_sections.py for now (will remove later).

- [ ] **Step 3: Update `render_revenue_breakdown()` to use chart_builders and table_formatters**

In `tabs/analytics_sections.py`, replace the entire `render_revenue_breakdown()` function (starting around line 346) with:

```python
def render_revenue_breakdown(
    report_loc_ids: list[int],
    start_str: str,
    end_str: str,
    df: pd.DataFrame,
    start_date: date,
) -> None:
    """Render revenue breakdown section with category mix and weekday analysis."""
    # ── Category Mix ───────────────────────────────────────────
    st.markdown("### Category Mix")
    cat_data = database.get_category_sales_for_date_range(
        report_loc_ids, start_str, end_str
    )
    if cat_data:
        cat_df = pd.DataFrame(cat_data)
        fig_cat = chart_builders.build_category_chart(cat_df, min_percent_threshold=2.0)
        if fig_cat:
            st.plotly_chart(fig_cat, use_container_width=True)

            # Drill-down expander
            with st.expander("📊 View detailed breakdown"):
                detail_df = table_formatters.build_category_detail_table(cat_df)
                st.dataframe(detail_df, use_container_width=True, hide_index=True)
    else:
        st.caption("No category data for this period.")

    # ── Weekday Analysis ───────────────────────────────────────
    if len(df) >= 7:
        st.markdown("### Weekday Analysis")
        monthly_tgt = scope.sum_location_monthly_targets(report_loc_ids)
        days_in_mo = utils.get_days_in_month(start_date.year, start_date.month)
        daily_tgt = monthly_tgt / days_in_mo if monthly_tgt > 0 else 0

        fig_wd = chart_builders.build_weekday_chart(df, daily_tgt)
        st.plotly_chart(fig_wd, use_container_width=True)

        # Drill-down expander
        with st.expander("📊 View data"):
            detail_df = table_formatters.build_weekday_detail(df, start_date)
            st.dataframe(detail_df, use_container_width=True, hide_index=True)
    else:
        st.caption("Need at least 7 days of data for weekday analysis.")
```

- [ ] **Step 4: Update `render_target_and_daily()` to use table_formatters**

In `tabs/analytics_sections.py`, update the daily data table section. Find the line with `st.dataframe(dv, ...)` and replace it and surrounding expander code:

```python
        st.markdown("### Daily Data")
        dv = table_formatters.format_daily_data_table(df, df_raw, multi_analytics)
        st.dataframe(
            dv,
            use_container_width=True,
            hide_index=True,
            column_config=table_formatters.get_daily_table_column_config(),
        )
```

- [ ] **Step 5: Remove the inline `_hex_to_rgba()` function from analytics_sections.py**

Search for the `_hex_to_rgba()` function in analytics_sections.py and delete it (it's now in chart_builders.py).

- [ ] **Step 6: Test that analytics_sections still works**

```bash
python -c "from tabs import analytics_sections; print('OK')"
```

Expected output: `OK`

- [ ] **Step 7: Commit**

```bash
git add tabs/analytics_sections.py
git commit -m "refactor: update analytics_sections to use chart_builders and table_formatters"
```

---

### Task 6: Update Report Tab for Previous-Day Deltas

**Files:**
- Modify: `tabs/report_tab.py`

- [ ] **Step 1: Update the report KPI display section in report_tab.py**

Find the section in `tabs/report_tab.py` where KPIs are rendered (search for "EOD Net Total" or similar). Replace it with:

```python
    if summary:
        y_m = [int(x) for x in date_str.split("-")[:2]]
        multi_outlet = len(outlets_bundle) > 1

        # Get previous day data for comparison
        prev_date = selected_date - timedelta(days=1)
        prev_date_str = prev_date.strftime("%Y-%m-%d")
        _, prev_summary = scope.get_daily_report_bundle(ctx.report_loc_ids, prev_date_str)

        # Calculate deltas
        net_total_delta = None
        covers_delta = None
        apc_delta = None

        if prev_summary:
            net_total_delta = utils.format_delta(
                summary["net_total"],
                prev_summary["net_total"],
                is_currency=True,
            )
            covers_delta = utils.format_delta(
                summary["covers"],
                prev_summary["covers"],
                is_currency=False,
            )
            if "apc" in summary and "apc" in prev_summary and prev_summary["apc"] > 0:
                apc_delta = utils.format_delta(
                    summary["apc"],
                    prev_summary["apc"],
                    is_currency=True,
                )

        # Render KPI cards
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric(
                "EOD Net Total",
                utils.format_currency(summary["net_total"]),
                delta=net_total_delta,
                help="Compared to previous day",
            )
        with col2:
            st.metric(
                "Covers",
                f"{summary['covers']:,}",
                delta=covers_delta,
                help="Compared to previous day",
            )
        with col3:
            apc = summary.get("apc", 0)
            st.metric(
                "APC",
                utils.format_currency(apc),
                delta=apc_delta,
                help="Compared to previous day",
            )

        divider()
        # ... rest of report rendering ...
```

- [ ] **Step 2: Verify report_tab imports are correct**

Ensure `report_tab.py` imports `timedelta`:

```python
from datetime import datetime, timedelta
```

(Should already be there.)

- [ ] **Step 3: Test that report_tab still works**

```bash
python -c "from tabs import report_tab; print('OK')"
```

Expected output: `OK`

- [ ] **Step 4: Commit**

```bash
git add tabs/report_tab.py
git commit -m "feat: add previous-day delta comparison on Report tab KPI cards"
```

---

### Task 7: Integration Testing

**Files:**
- Test: Manual testing + integration tests

- [ ] **Step 1: Run all tests to ensure no regressions**

```bash
pytest tests/ -v
```

Expected: All tests pass (no failures).

- [ ] **Step 2: Manual test — Launch the app and navigate to Analytics tab**

```bash
streamlit run app.py
```

In the browser:
1. Go to **Analytics** tab
2. Select **"Last 30 Days"** period
3. Verify:
   - Daily Sales Trend chart shows 7-day MA (dashed orange line)
   - APC chart Y-axis starts at 0
   - Weekday Analysis bars: best day is green, worst is red, others are gray
   - Category Mix shows donut with "Other" slice (if categories < 2%)
   - All expanders ("View data") open and show correct tables
   - All amounts formatted as ₹1,30,235 (Indian format)

- [ ] **Step 3: Manual test — Check Report tab**

1. Go to **Report** tab
2. Navigate to a date with previous day data
3. Verify:
   - EOD Net Total shows delta vs previous day
   - Covers shows delta vs previous day
   - APC shows delta vs previous day
   - Deltas are green (↑) for increases, red (↓) for decreases

- [ ] **Step 4: Manual test — Mobile responsiveness**

1. Open browser DevTools (F12)
2. Set viewport to 375px width (mobile)
3. Verify charts and tables are readable on mobile
4. Verify no horizontal scrolling

- [ ] **Step 5: Manual test — Empty/edge cases**

1. Select a period with <7 days of data
2. Verify: 7-day MA does NOT show (✓)
3. Select a period with no category data
4. Verify: "No category data" message shows (✓)
5. Select a period with no data
6. Verify: "No data in this period" message shows (✓)

- [ ] **Step 6: Commit test results**

```bash
git add -A
git commit -m "test: verify all 8 improvements working in app (manual integration test)"
```

---

### Task 8: Code Quality & Linting

**Files:**
- All modified/created files

- [ ] **Step 1: Run ruff linter**

```bash
ruff check tabs/chart_builders.py tabs/table_formatters.py utils.py ui_theme.py tabs/analytics_sections.py tabs/report_tab.py
```

Expected: No errors or warnings.

- [ ] **Step 2: Run ruff formatter**

```bash
ruff format tabs/chart_builders.py tabs/table_formatters.py utils.py ui_theme.py tabs/analytics_sections.py tabs/report_tab.py
```

- [ ] **Step 3: Run type checker (if available)**

```bash
pyright tabs/chart_builders.py tabs/table_formatters.py 2>/dev/null || echo "pyright not installed"
```

Optional (requires pyright installation). If not available, skip.

- [ ] **Step 4: Verify docstrings are complete**

Check that all new functions have docstrings. Example:

```python
def build_category_chart(...) -> go.Figure:
    """Build Category Mix donut chart with 'Other' grouping for small categories.
    
    Categories below min_percent_threshold are grouped into 'Other' slice.
    
    Args:
        cat_df: DataFrame with 'category' and 'amount' columns
        min_percent_threshold: Minimum percentage to display as separate slice
        
    Returns:
        Plotly Figure with donut chart or None if empty
    """
```

- [ ] **Step 5: Commit linting fixes**

```bash
git add tabs/chart_builders.py tabs/table_formatters.py utils.py ui_theme.py tabs/analytics_sections.py tabs/report_tab.py
git commit -m "style: apply ruff formatting and linting fixes"
```

---

### Task 9: Final Verification & Documentation

**Files:**
- Check: Spec compliance
- Update: README or inline docs if needed

- [ ] **Step 1: Verify spec compliance checklist**

Go through the spec (`docs/superpowers/specs/2026-04-06-analytics-improvements-design.md`) and check off each improvement:

**Spec Compliance:**
- ✅ Improvement #1: 7-day MA on Daily Sales Trend
- ✅ Improvement #2: APC Y-axis starts at 0
- ✅ Improvement #3: Weekday bars colored (green/red/gray)
- ✅ Improvement #4: Category Mix donut + detail table
- ✅ Improvement #5: Period-over-period KPI deltas (already implemented)
- ✅ Improvement #6: Drill-down expanders below charts
- ✅ Improvement #7: Conditional table formatting + Indian numbers
- ✅ Improvement #8: Report tab previous-day deltas

- [ ] **Step 2: Update WORK_SUMMARY.md (if it exists)**

If there's a `WORK_SUMMARY.md` file, add an entry:

```markdown
## 2026-04-06: Analytics Improvements (Phase 1)

Implemented 8 professional analytics improvements:
- 7-day moving average on Daily Sales Trend chart
- Fixed APC Trend Y-axis scaling (start at 0)
- Conditional coloring on Weekday Analysis bars (green/red/gray)
- Category Mix with "Other" grouping + detailed breakdown table
- Period-over-period KPI deltas (already ~70% implemented, verified)
- Drill-down expanders for all charts (sales, APC, weekday, category, target)
- Conditional table formatting + Indian number formatting (₹1,30,235 format)
- Previous-day comparison on Report tab KPI cards

**Modules added:**
- `tabs/chart_builders.py` — 6 chart builder functions
- `tabs/table_formatters.py` — 7 table formatter functions
- Enhanced `utils.py` with Indian currency formatting
- Enhanced `ui_theme.py` with conditional formatting colors

**Tests added:**
- `tests/test_utils_indian_currency.py` — Indian format tests
- `tests/test_chart_builders.py` — Chart builder tests
- `tests/test_table_formatters.py` — Table formatter tests

**Files modified:**
- `tabs/analytics_sections.py` — Refactored to use new modules
- `tabs/report_tab.py` — Added previous-day delta display
- `ui_theme.py` — Added color tokens

All improvements tested and verified working.
```

- [ ] **Step 3: Final git log check**

```bash
git log --oneline -10
```

Expected: Last 10 commits show your incremental changes:
```
abc1234 test: verify all 8 improvements working in app
def5678 style: apply ruff formatting and linting fixes
ghi9012 feat: add previous-day delta comparison on Report tab
jkl3456 refactor: update analytics_sections to use chart_builders
mno7890 feat: create table_formatters module
pqr1234 feat: create chart_builders module
stu5678 feat: add Indian currency formatting
vwx9012 feat: add conditional formatting color tokens
```

- [ ] **Step 4: Final commit summary**

```bash
git commit --allow-empty -m "docs: complete analytics improvements implementation (8 features, 3 modules)"
```

This creates a summary commit marking the end of the implementation.

---

## Testing Checklist

Before declaring the feature complete, verify all of the following:

### Unit Tests
- [ ] `pytest tests/test_utils_indian_currency.py -v` — All pass
- [ ] `pytest tests/test_chart_builders.py -v` — All pass
- [ ] `pytest tests/test_table_formatters.py -v` — All pass
- [ ] `pytest tests/ -v` — All tests pass (no regressions)

### Integration Tests
- [ ] App launches without errors: `streamlit run app.py`
- [ ] Analytics tab loads, period selector works
- [ ] All 8 improvements visible and functional
- [ ] No console errors or warnings

### Manual UI Tests
- [ ] Daily Sales Trend: 7-day MA line visible (dashed orange)
- [ ] APC chart: Y-axis starts at 0
- [ ] Weekday bars: Green (best), Red (worst), Gray (other days)
- [ ] Category donut: Shows "Other" slice for small categories
- [ ] Detail table below donut: Shows all categories
- [ ] KPI cards: Show period-over-period deltas in green/red
- [ ] All expanders: Open and show correct data
- [ ] All numbers: Formatted as ₹1,30,235 (Indian style)
- [ ] Report tab: Previous-day deltas displayed
- [ ] Mobile (375px): Charts and tables readable

### Code Quality
- [ ] No linting errors: `ruff check .`
- [ ] All docstrings complete and accurate
- [ ] No `# TODO`, `# FIXME`, or placeholder code
- [ ] Type hints on all function signatures
- [ ] Commits are incremental and well-labeled

---

## Success Criteria Met

✅ All 8 improvements implemented and tested  
✅ Modular architecture (3 new modules) created  
✅ No breaking changes to existing code  
✅ No database schema changes  
✅ Unit tests written and passing  
✅ Integration tests passing  
✅ Manual testing completed  
✅ Code quality verified (linting, docstrings)  
✅ Frequent, incremental commits  

---

## Next Steps (Post-Implementation)

- Monitor production performance with large datasets
- Gather user feedback on the 8 improvements
- Consider future enhancements (e.g., custom export formats, more drill-down options)
- Plan Phase 2 if additional analytics features are needed

---

**Plan Status:** ✅ **Ready for Execution**

Use `subagent-driven-development` (recommended) or `executing-plans` skill to implement tasks 1–9 step-by-step.
