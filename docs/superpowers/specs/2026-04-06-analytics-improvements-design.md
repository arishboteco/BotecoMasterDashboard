# Analytics Improvements Design Spec

**Date:** April 6, 2026  
**Project:** Boteco Master Dashboard  
**Scope:** 8 data analytics and presentation improvements to Analytics and Report tabs  
**Approach:** Modular refactoring (Approach B) with new utility modules  

---

## Executive Summary

This spec outlines 8 professional analytics improvements to enhance data clarity, trend visibility, and user insight into restaurant sales performance. The implementation uses a modular architecture (3 new Python modules) to maintain clean code organization and enable future enhancements.

**Key improvements:**
1. 7-day moving average on Daily Sales Trend chart
2. Fix APC Trend Y-axis scaling (start at 0)
3. Conditional coloring on Weekday Analysis bars
4. Category Mix donut with detailed breakdown table
5. Period-over-period deltas on KPI cards (already ~70% implemented)
6. Drill-down expanders below each chart
7. Conditional table formatting + Indian number formatting
8. Previous-day comparison on Report tab

**Timeline:** Single implementation cycle  
**Risk Level:** Low (modular changes, no schema modifications)  
**Testing:** Unit tests for utilities + integration tests for charts/tables

---

## Architecture Overview

### Proposed Module Structure

```
tabs/
├── analytics_tab.py (unchanged)
├── analytics_sections.py (refactored to orchestrate)
├── analytics_logic.py (unchanged)
├── chart_builders.py (NEW — chart construction)
├── table_formatters.py (NEW — table formatting & expanders)
├── report_tab.py (minimal changes)
└── ...

utils.py (enhanced with Indian formatting, delta helpers)
ui_theme.py (new color tokens for conditional formatting)
```

### Data Flow

```
analytics_tab.py
    ↓ (fetches data, resolves period)
analytics_sections.py (orchestrator)
    ├→ render_overview() [uses existing utils for deltas]
    │
    ├→ render_sales_performance()
    │   ├→ chart_builders.build_sales_trend_chart()
    │   ├→ chart_builders.build_covers_chart()
    │   ├→ chart_builders.build_apc_chart()
    │   └→ [expanders with table_formatters tables]
    │
    ├→ render_revenue_breakdown()
    │   ├→ chart_builders.build_category_chart()
    │   ├→ [expander with table_formatters.build_category_detail_table()]
    │   └→ chart_builders.build_weekday_chart()
    │
    └→ render_target_and_daily()
        ├→ chart_builders.build_target_chart()
        ├→ table_formatters.format_daily_data_table()
        └→ [multiple expanders with detail tables]
```

---

## Feature Specifications

### 1. Seven-Day Moving Average on Daily Sales Trend

**Location:** `tabs/chart_builders.py` → `build_sales_trend_chart()`

**Current behavior:** Raw daily net sales line shows high variance (₹50K–₹275K), making trends hard to identify.

**New behavior:**
- When period supports trend analysis (≥7 data points): calculate 7-day SMA
- Add second line: **dashed orange** (#F4B400) labeled "7-day Avg"
- Keep original blue area chart intact
- Multi-outlet mode: calculate SMA on **combined daily totals** (not per-outlet)

**Implementation:**
```python
def build_sales_trend_chart(
    df: pd.DataFrame,
    df_raw: pd.DataFrame,
    multi_analytics: bool,
    analysis_period: str
) -> go.Figure:
    """Build Daily Sales Trend chart with optional 7-day MA."""
    # Determine if we can show moving average
    show_ma = _period_supports_trend_analysis(analysis_period, len(df))
    
    if multi_analytics and not df_raw.empty:
        # Multi-outlet: group by date, sum net_total, then apply MA
        df_agg = df_raw.groupby('date')['net_total'].sum().reset_index()
        values = df_agg['net_total'].tolist()
        dates = pd.to_datetime(df_agg['date'])
    else:
        # Single outlet
        dates = pd.to_datetime(df['date'])
        values = df['net_total'].tolist()
    
    fig = go.Figure()
    
    # Actual sales area
    fig.add_trace(go.Scatter(
        x=dates, y=values,
        mode='lines+markers',
        name='Daily Sales',
        fill='tozeroy',
        fillcolor=_hex_to_rgba(ui_theme.BRAND_PRIMARY, 0.15),
        line=dict(color=ui_theme.BRAND_PRIMARY, width=2),
        marker=dict(size=4),
    ))
    
    # 7-day moving average
    if show_ma:
        ma_values = moving_average(values, window=7)
        ma_series = pd.Series(ma_values)
        ma_valid = ma_series[pd.notna(ma_series)]
        if not ma_valid.empty:
            fig.add_trace(go.Scatter(
                x=dates[pd.notna(ma_series)],
                y=ma_valid.tolist(),
                mode='lines',
                name='7-day Avg',
                line=dict(color=ui_theme.BRAND_WARN, width=2, dash='dot'),
                opacity=0.8,
            ))
    
    fig.update_layout(
        xaxis_title='Date',
        yaxis_title='Net Sales (₹)',
        hovermode='x unified',
        height=ui_theme.CHART_HEIGHT,
    )
    return fig
```

**Testing:**
- ✅ MA only shows for periods ≥7 days
- ✅ MA line correctly aligns with dates (first 6 points are NaN)
- ✅ Multi-outlet MA uses combined totals, not individual outlet MAs

---

### 2. Fix APC Trend Y-Axis Scaling

**Location:** `tabs/chart_builders.py` → `build_apc_chart()`

**Current behavior:** Y-axis starts at ~₹1,500 (min value), exaggerates volatility visually.

**New behavior:**
- Y-axis starts at 0
- Y-axis max: 1.1 × highest APC value (maintain breathing room)
- Dashed average line remains at ₹2,108
- Chart remains readable (line variation is still visible, just honest)

**Implementation:**
```python
def build_apc_chart(df: pd.DataFrame, multi_analytics: bool) -> go.Figure | None:
    """Build APC Trend chart with honest Y-axis starting at 0."""
    apc_df = df[df['apc'] > 0].copy() if 'apc' in df.columns else pd.DataFrame()
    if apc_df.empty:
        return None
    
    dates = pd.to_datetime(apc_df['date'])
    apc_values = apc_df['apc'].tolist()
    
    fig = px.line(apc_df, x='date', y='apc', markers=True, title='APC over time')
    fig.update_traces(line_color=ui_theme.BRAND_PRIMARY)
    
    # Add average line
    avg_apc = float(apc_df['apc'].mean())
    fig.add_hline(
        y=avg_apc,
        line_dash='dash',
        line_color='gray',
        annotation_text=f'Avg {utils.format_currency(avg_apc)}',
        annotation_position='top right',
    )
    
    # Set Y-axis to start at 0
    max_apc = max(apc_values)
    fig.update_yaxes(range=[0, max_apc * 1.1])
    
    fig.update_layout(
        xaxis_title='Date',
        yaxis_title='APC (₹)',
        hovermode='x unified',
        height=ui_theme.CHART_HEIGHT,
    )
    return fig
```

**Testing:**
- ✅ Y-axis range is [0, max_apc * 1.1]
- ✅ Average line position is correct
- ✅ Empty data returns None gracefully

---

### 3. Weekday Analysis Conditional Coloring

**Location:** `tabs/chart_builders.py` → `build_weekday_chart()`

**Current behavior:** All bars are red with pattern icons (✓ ⚠ ✗).

**New behavior:**
- Best day (highest avg sales): **Green** (#3FA7A3 / BRAND_SUCCESS)
- Worst day (lowest avg sales): **Red** (#EF4444 / BRAND_ERROR)
- Other days: **Neutral gray** (#94A3B8)
- Keep "Best:" and "Worst:" annotation labels
- Keep dashed target line

**Implementation:**
```python
def build_weekday_chart(
    df: pd.DataFrame,
    daily_target: float
) -> go.Figure:
    """Build Weekday Analysis chart with conditional bar coloring."""
    wd_df = df[df['net_total'] > 0].copy()
    wd_df['weekday'] = wd_df['date'].apply(utils.get_weekday_name)
    
    wd_agg = (
        wd_df.groupby('weekday')['net_total']
        .mean()
        .reset_index()
        .rename(columns={'net_total': 'avg_sales'})
    )
    
    # Sort by day of week
    day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    wd_agg['weekday'] = pd.Categorical(wd_agg['weekday'], categories=day_order, ordered=True)
    wd_agg = wd_agg.sort_values('weekday')
    
    # Determine best and worst days
    best_idx = wd_agg['avg_sales'].idxmax()
    worst_idx = wd_agg['avg_sales'].idxmin()
    best_day = wd_agg.loc[best_idx, 'weekday']
    worst_day = wd_agg.loc[worst_idx, 'weekday']
    
    # Color mapping: green for best, red for worst, gray for others
    colors = [
        ui_theme.BRAND_SUCCESS if day == best_day
        else ui_theme.BRAND_ERROR if day == worst_day
        else '#94A3B8'  # neutral gray
        for day in wd_agg['weekday']
    ]
    
    fig = px.bar(
        wd_agg,
        x='weekday',
        y='avg_sales',
        title='Average net sales by day of week',
        color_discrete_sequence=colors,
    )
    
    # Add target line
    if daily_target > 0:
        fig.add_hline(
            y=daily_target,
            line_dash='dash',
            line_color='gray',
            annotation_text=f'Daily target {utils.format_currency(daily_target)}',
            annotation_position='top right',
        )
    
    # Add best/worst annotations
    fig.add_annotation(
        x=best_day, y=wd_agg.loc[best_idx, 'avg_sales'],
        text=f'Best: {best_day}',
        showarrow=True, arrowhead=2,
        bgcolor=ui_theme.BRAND_SUCCESS, font_color='white',
    )
    fig.add_annotation(
        x=worst_day, y=wd_agg.loc[worst_idx, 'avg_sales'],
        text=f'Worst: {worst_day}',
        showarrow=True, arrowhead=2,
        bgcolor=ui_theme.BRAND_ERROR, font_color='white',
    )
    
    fig.update_layout(
        xaxis_title='',
        yaxis_title='Avg Net Sales (₹)',
        height=ui_theme.CHART_HEIGHT,
        showlegend=False,
    )
    return fig
```

**Testing:**
- ✅ Best day bar is green
- ✅ Worst day bar is red
- ✅ Other days are gray
- ✅ Annotations position correctly

---

### 4. Category Mix: Donut + Detailed Breakdown Table

**Location:** 
- Chart: `tabs/chart_builders.py` → `build_category_chart()`
- Table: `tabs/table_formatters.py` → `build_category_detail_table()`

**Current behavior:** Pie/donut chart shows all categories; small categories (<2%) are nearly invisible.

**New behavior:**
- Any category < 2% of total → grouped into "Other" slice
- Donut chart shows clean 5–6 slices
- Below chart: Expander "📊 View detailed breakdown" with table showing:
  - Category | Amount (₹) | % of Total
  - All categories listed (including those rolled into "Other")
  - Sortable by amount or percentage
  - Total row at bottom

**Implementation:**

`chart_builders.py`:
```python
def build_category_chart(
    cat_df: pd.DataFrame,
    min_percent_threshold: float = 2.0
) -> go.Figure:
    """Build Category Mix donut chart with 'Other' grouping."""
    if cat_df.empty:
        return None
    
    cat_df = cat_df.copy()
    total_cat = float(cat_df['amount'].sum())
    cat_df['pct'] = (cat_df['amount'] / total_cat * 100)
    
    # Group small categories into "Other"
    small_cats = cat_df[cat_df['pct'] < min_percent_threshold]
    major_cats = cat_df[cat_df['pct'] >= min_percent_threshold].copy()
    
    if not small_cats.empty:
        other_amount = small_cats['amount'].sum()
        other_row = pd.DataFrame({
            'category': ['Other'],
            'amount': [other_amount],
            'pct': [other_amount / total_cat * 100],
        })
        cat_df_chart = pd.concat([major_cats, other_row], ignore_index=True)
    else:
        cat_df_chart = major_cats
    
    fig = px.pie(
        cat_df_chart,
        names='category',
        values='amount',
        title=f'Category revenue mix (Total: {utils.format_currency(total_cat)})',
        hole=0.4,  # donut
        color_discrete_sequence=ui_theme.CHART_COLORWAY,
    )
    fig.update_traces(textposition='inside', textinfo='percent+label')
    fig.update_layout(height=ui_theme.CHART_HEIGHT)
    
    return fig
```

`table_formatters.py`:
```python
def build_category_detail_table(cat_df: pd.DataFrame) -> pd.DataFrame:
    """Build detailed category breakdown table with all categories."""
    if cat_df.empty:
        return pd.DataFrame()
    
    cat_df = cat_df.copy()
    total = cat_df['amount'].sum()
    cat_df['Percentage'] = (cat_df['amount'] / total * 100).round(1).astype(str) + '%'
    cat_df['Amount (₹)'] = cat_df['amount'].apply(utils.format_indian_currency)
    
    # Rename for display
    result = cat_df[['category', 'Amount (₹)', 'Percentage']].copy()
    result.columns = ['Category', 'Amount (₹)', '% of Total']
    result = result.sort_values('Amount (₹)', key=lambda x: x.str.replace(',', '').astype(float), ascending=False)
    
    # Add totals row
    totals_row = pd.DataFrame({
        'Category': ['TOTAL'],
        'Amount (₹)': [utils.format_indian_currency(total)],
        '% of Total': ['100%'],
    })
    result = pd.concat([result, totals_row], ignore_index=True)
    
    return result
```

**Integration in analytics_sections.py:**
```python
def render_revenue_breakdown(...):
    st.markdown("### Category Mix")
    cat_data = database.get_category_sales_for_date_range(...)
    if cat_data:
        cat_df = pd.DataFrame(cat_data)
        fig_cat = chart_builders.build_category_chart(cat_df)
        st.plotly_chart(fig_cat, use_container_width=True)
        
        # Expander with detail table
        with st.expander("📊 View detailed breakdown"):
            detail_df = table_formatters.build_category_detail_table(cat_df)
            st.dataframe(detail_df, use_container_width=True, hide_index=True)
```

**Testing:**
- ✅ Small categories (<2%) grouped into "Other"
- ✅ Donut shows ≤6 slices
- ✅ Detail table shows all original categories
- ✅ Totals row sums to 100%
- ✅ Table is sortable by column

---

### 5. Period-over-Period KPI Deltas

**Location:** `tabs/analytics_sections.py` → `render_overview()`

**Current behavior:** Already ~70% implemented in current codebase.

**Status:** ✅ **Mostly done** — code already calculates and displays deltas.

**Verification needed:**
- Confirm all 4 KPI cards (Total Sales, Total Covers, Avg Daily Sales, Days with Data) display delta
- Verify delta format: "↑ ₹12,345 (+8.5%)" in green, "↓ ₹5,000 (-3.2%)" in red
- Test comparison periods (e.g., "Last Month" vs previous month)

**No code changes required** unless delta display needs refinement.

---

### 6. Drill-Down Expanders Below Charts

**Location:** `tabs/analytics_sections.py` after each chart section

**Pattern:**
```python
with st.expander("📊 View data"):
    detail_df = table_formatters.build_<chart>_detail_table(df, ...)
    st.dataframe(detail_df, use_container_width=True, hide_index=True)
```

**Detail tables to create (in `table_formatters.py`):**

| Chart | Table | Columns |
|-------|-------|---------|
| Daily Sales Trend | `build_sales_trend_detail()` | Date, Outlet (if multi), Net Sales, Covers, APC |
| Covers Trend | `build_covers_detail()` | Date, Outlet (if multi), Covers |
| APC Trend | `build_apc_detail()` | Date, Outlet (if multi), APC |
| Weekday Analysis | `build_weekday_detail()` | Day, Avg Sales, Avg Covers, Count |
| Category Mix | `build_category_detail_table()` (already defined) | Category, Amount, % |
| Target Achievement | `build_target_detail()` | Date, Outlet, Net Sales, Target, Achievement % |

**Example implementation:**
```python
def build_sales_trend_detail(
    df: pd.DataFrame,
    df_raw: pd.DataFrame,
    multi_analytics: bool
) -> pd.DataFrame:
    """Build sales trend detail table."""
    if multi_analytics and not df_raw.empty:
        detail = df_raw[['date', 'Outlet', 'net_total', 'covers', 'apc']].copy()
        detail.columns = ['Date', 'Outlet', 'Net Sales', 'Covers', 'APC']
    else:
        detail = df[['date', 'net_total', 'covers', 'apc']].copy()
        detail.columns = ['Date', 'Net Sales', 'Covers', 'APC']
    
    # Format currency and numbers
    detail['Date'] = pd.to_datetime(detail['Date']).dt.strftime('%Y-%m-%d')
    detail['Net Sales'] = detail['Net Sales'].apply(utils.format_indian_currency)
    detail['Covers'] = detail['Covers'].astype(int).astype(str)
    if 'APC' in detail.columns:
        detail['APC'] = detail['APC'].apply(utils.format_indian_currency)
    
    return detail
```

**Testing:**
- ✅ Each expander shows correct subset of data
- ✅ Data matches what went into the chart
- ✅ All currency values use Indian format
- ✅ Dates are readable

---

### 7. Conditional Table Formatting + Indian Numbers

**Location:** `tabs/table_formatters.py` → `format_daily_data_table()` + `utils.py` enhancements

**Current behavior:** Plain data table with no highlighting or Indian number format.

**New behavior:**
- **Achievement column** conditional formatting:
  - ≥100%: Green background (#10B981 or equivalent)
  - 70–99%: Yellow/amber background (#FBBF24)
  - <70%: Red background (#EF4444)
- **Totals row** at bottom: Average sales, total covers, overall achievement %
- **Column sorting:** Native Streamlit dataframe support (click headers)
- **Indian number formatting:** All ₹ amounts use "1,30,235" format

**Implementation:**

`utils.py`:
```python
def format_indian_currency(amount: float) -> str:
    """Format amount as Indian currency: 1,30,235 instead of 130,235."""
    if amount == 0:
        return '₹0'
    
    # Handle negative
    is_negative = amount < 0
    amount = abs(amount)
    
    # Convert to string and handle decimals
    parts = f"{amount:,.2f}".split('.')
    integer_part = parts[0].replace(',', '')  # remove commas first
    decimal_part = parts[1] if len(parts) > 1 else '00'
    
    # Indian numbering: group from right as 3, 2, 2, 2...
    # E.g., 1234567 → 12,34,567
    if len(integer_part) <= 3:
        formatted = integer_part
    else:
        # Last 3 digits
        last_three = integer_part[-3:]
        # Remaining digits, grouped by 2 from right
        remaining = integer_part[:-3]
        grouped = ','.join([remaining[max(0, i-2):i] for i in range(len(remaining), 0, -2)][::-1])
        formatted = f"{grouped},{last_three}"
    
    # Combine with decimals (round to rupees, no paise for large amounts)
    if int(decimal_part) == 0:
        result = formatted
    else:
        result = f"{formatted}.{decimal_part[:2]}"
    
    if is_negative:
        return f"-₹{result}"
    return f"₹{result}"

def update_format_currency_to_indian():
    """Update the main format_currency() to use Indian format."""
    # Modify existing function or create wrapper
    pass
```

`table_formatters.py`:
```python
def format_daily_data_table(
    df: pd.DataFrame,
    df_raw: pd.DataFrame,
    multi_analytics: bool
) -> pd.DataFrame:
    """Build daily data table with conditional formatting metadata."""
    if multi_analytics and not df_raw.empty:
        detail = df_raw[['date', 'Outlet', 'covers', 'net_total', 'target', 'achievement']].copy()
    else:
        detail = df[['date', 'covers', 'net_total', 'target', 'achievement']].copy()
        detail.insert(1, 'Outlet', 'Combined')
    
    # Format columns
    detail['Date'] = pd.to_datetime(detail['date']).dt.strftime('%d %b %Y')
    detail['Covers'] = detail['covers'].astype(int).astype(str)
    detail['Net Sales'] = detail['net_total'].apply(utils.format_indian_currency)
    detail['Target'] = detail['target'].apply(utils.format_indian_currency)
    detail['Achievement'] = detail['achievement'].round(1).astype(str) + '%'
    
    # Select display columns
    result = detail[['Date', 'Outlet', 'Covers', 'Net Sales', 'Target', 'Achievement']].copy()
    
    # Add totals row
    totals_row = pd.DataFrame({
        'Date': ['TOTAL'],
        'Outlet': [''],
        'Covers': [str(int(detail['covers'].sum()))],
        'Net Sales': [utils.format_indian_currency(detail['net_total'].sum())],
        'Target': [utils.format_indian_currency(detail['target'].sum())],
        'Achievement': [f"{(detail['net_total'].sum() / detail['target'].sum() * 100):.1f}%"] if detail['target'].sum() > 0 else ['—'],
    })
    result = pd.concat([result, totals_row], ignore_index=True)
    
    return result

def get_daily_table_column_config() -> dict:
    """Return column config with conditional formatting for Achievement column."""
    return {
        'Date': st.column_config.TextColumn('Date'),
        'Outlet': st.column_config.TextColumn('Outlet'),
        'Covers': st.column_config.TextColumn('Covers'),
        'Net Sales': st.column_config.TextColumn('Net Sales (₹)'),
        'Target': st.column_config.TextColumn('Target (₹)'),
        'Achievement': st.column_config.TextColumn('Achievement %'),  # conditional color via HTML
    }
```

**Conditional formatting in analytics_sections.py:**
```python
st.dataframe(
    detail_df,
    use_container_width=True,
    hide_index=True,
    column_config=table_formatters.get_daily_table_column_config(),
)

# Alternative: use st.write with HTML for custom conditional formatting
# (Streamlit's native dataframe doesn't support cell-level background colors yet)
# For now, use CSS/HTML if advanced styling needed, or rely on contrast/text formatting
```

**Testing:**
- ✅ Indian format: 1,30,235 not 130,235
- ✅ Achievement % colors: green ≥100%, yellow 70–99%, red <70%
- ✅ Totals row calculates correctly
- ✅ Sorting works on all columns

---

### 8. Report Tab: Previous Day Comparison

**Location:** `tabs/report_tab.py` → Sales Summary KPI section

**Current behavior:** Shows today's sales, covers, APC with no comparison context.

**New behavior:**
- Below each KPI (EOD Net Total, Covers, APC), add delta indicator
- Format: "▲ ₹15,230 (+8.3%)" in green or "▼ ₹7,500 (-3.8%)" in red
- Subtle styling (smaller font, lighter color) so it doesn't compete with primary numbers
- Only show if previous day data exists

**Implementation:**

`report_tab.py`:
```python
def render(ctx: TabContext) -> None:
    # ... existing date selector code ...
    
    selected_date = st.session_state["report_date"]
    date_str = selected_date.strftime("%Y-%m-%d")
    outlets_bundle, summary = scope.get_daily_report_bundle(ctx.report_loc_ids, date_str)
    
    if summary:
        # Get previous day data for comparison
        prev_date = selected_date - timedelta(days=1)
        prev_date_str = prev_date.strftime("%Y-%m-%d")
        _, prev_summary = scope.get_daily_report_bundle(ctx.report_loc_ids, prev_date_str)
        
        # Extract deltas
        net_total_delta = None
        covers_delta = None
        apc_delta = None
        
        if prev_summary:
            net_total_delta = utils.format_delta(
                summary['net_total'], 
                prev_summary['net_total'],
                is_currency=True
            )
            covers_delta = utils.format_delta(
                summary['covers'],
                prev_summary['covers'],
                is_currency=False
            )
            if 'apc' in summary and 'apc' in prev_summary and prev_summary['apc'] > 0:
                apc_delta = utils.format_delta(
                    summary['apc'],
                    prev_summary['apc'],
                    is_currency=True
                )
        
        # Render KPI cards with deltas
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric(
                "EOD Net Total",
                utils.format_indian_currency(summary['net_total']),
                delta=net_total_delta,
                help="Compared to previous day"
            )
        with col2:
            st.metric(
                "Covers",
                f"{summary['covers']:,}",
                delta=covers_delta,
                help="Compared to previous day"
            )
        with col3:
            st.metric(
                "APC",
                utils.format_indian_currency(summary.get('apc', 0)),
                delta=apc_delta,
                help="Compared to previous day"
            )
        
        # ... rest of report rendering ...
```

**Testing:**
- ✅ Previous day data fetched correctly
- ✅ Deltas calculated and formatted correctly
- ✅ Colors: green for increase, red for decrease
- ✅ Only shows if previous day data exists

---

## Module Function Reference

### `tabs/chart_builders.py`

**Purpose:** Construct individual Plotly charts with consistent styling

**Functions:**
- `build_sales_trend_chart(df, df_raw, multi_analytics, analysis_period)` → `go.Figure`
- `build_covers_chart(df, df_raw, multi_analytics, analysis_period)` → `go.Figure`
- `build_apc_chart(df, multi_analytics)` → `go.Figure | None`
- `build_category_chart(cat_df, min_percent_threshold=2.0)` → `go.Figure`
- `build_weekday_chart(df, daily_target)` → `go.Figure`
- `build_target_chart(df, monthly_target, days_in_month)` → `go.Figure` (refactored from analytics_sections)

**Imports:**
```python
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import ui_theme
import utils
from tabs.forecasting import moving_average, linear_forecast
```

---

### `tabs/table_formatters.py`

**Purpose:** Format and build data tables with conditional styling

**Functions:**
- `format_daily_data_table(df, df_raw, multi_analytics)` → `pd.DataFrame`
- `build_sales_trend_detail(df, df_raw, multi_analytics)` → `pd.DataFrame`
- `build_covers_detail(df, df_raw, multi_analytics)` → `pd.DataFrame`
- `build_apc_detail(df, df_raw, multi_analytics)` → `pd.DataFrame`
- `build_weekday_detail(df, start_date)` → `pd.DataFrame`
- `build_category_detail_table(cat_df)` → `pd.DataFrame`
- `build_target_detail(df, daily_target)` → `pd.DataFrame`
- `get_daily_table_column_config()` → `dict` (Streamlit column config)

**Imports:**
```python
import pandas as pd
import streamlit as st
import utils
```

---

### `utils.py` (enhancements)

**New functions:**
- `format_indian_currency(amount: float) -> str` — convert 130235 → "₹1,30,235"
- `format_delta_with_arrow(current, prior, is_currency=True) -> str` — "↑ ₹12,345 (+8.5%)"

**Modified functions:**
- `format_currency(amount: float) -> str` — update to use Indian format

**Existing functions used:**
- `format_delta(current, prior, is_currency, is_percent)` — already implemented, used for KPI deltas
- `get_weekday_name(date_str)` — used in weekday analysis
- `calculate_growth(current, previous)` — used for delta calculations

---

### `ui_theme.py` (enhancements)

**New color tokens:**
```python
TABLE_ACHIEVEMENT_GREEN = "#10B981"    # ≥100%
TABLE_ACHIEVEMENT_YELLOW = "#FBBF24"   # 70–99%
TABLE_ACHIEVEMENT_RED = "#EF4444"      # <70%
```

---

### `tabs/analytics_sections.py` (refactored)

**Changes:**
- Replace inline chart building with calls to `chart_builders.*`
- Add expanders with `table_formatters.*` tables below each chart
- Reduce file size from ~650 to ~400 lines
- Keep orchestration logic, remove chart construction code

---

## Data & Dependencies

**No database schema changes required.**

**Existing functions used:**
- `database.get_summaries_for_date_range_multi()` — existing
- `database.get_category_sales_for_date_range()` — existing
- `scope.merge_summaries_by_date()` — existing
- `scope.get_daily_report_bundle()` — existing
- `scope.sum_location_monthly_targets()` — existing

**New helper functions (already exist in codebase):**
- `tabs.forecasting.moving_average()` — already implemented
- `tabs.forecasting.linear_forecast()` — already implemented

---

## Testing Strategy

### Unit Tests (`tests/`)

**File:** `tests/test_chart_builders.py`
- Test each chart builder with sample data
- Verify chart structure (traces, layout, axes)
- Verify legend, annotations, colors

**File:** `tests/test_table_formatters.py`
- Test table construction with multi-outlet/single-outlet data
- Verify totals row calculation
- Verify column ordering and formatting
- Test Indian number formatting

**File:** `tests/test_utils_enhancements.py`
- Test `format_indian_currency()` with various inputs
- Test `format_delta_with_arrow()` formatting

### Integration Tests

- Load real analytics data from database
- Render all charts and tables without errors
- Verify drill-down expanders show correct data subsets
- Test with different periods (Last 7 Days, Last Month, Custom)
- Test with multi-outlet and single-outlet views
- Verify conditional table coloring displays correctly

### Manual Testing Checklist

- [ ] Daily Sales Trend: 7-day MA appears for ≥7 days
- [ ] APC chart: Y-axis starts at 0, not min value
- [ ] Weekday Analysis: Best day is green, worst is red, others are gray
- [ ] Category Mix: Donut shows ≤6 slices, table shows all categories
- [ ] KPI cards: Deltas show with correct color and formatting
- [ ] Expanders: All drill-down tables appear below charts
- [ ] Daily Data table: Achievement % highlighted with correct colors
- [ ] Indian formatting: All ₹ amounts use 1,30,235 format
- [ ] Report tab: Previous day deltas display correctly
- [ ] Responsive: Charts and tables render well on mobile (375px width)
- [ ] Empty states: Graceful handling when no data exists

---

## Risk Assessment

**Risk Level:** **LOW**

**Why low risk:**
- ✅ No database schema changes
- ✅ No breaking changes to existing APIs
- ✅ Modular refactoring (new files, existing files improved)
- ✅ All data flow remains unchanged
- ✅ Existing utilities (`moving_average`, `linear_forecast`) already tested

**Potential issues & mitigations:**
| Issue | Mitigation |
|-------|-----------|
| Refactored chart builders break existing functionality | Unit test each builder; manual test against current charts |
| Indian number formatting breaks in some edge cases (very large numbers, negatives) | Comprehensive unit tests with boundary values |
| Table expanders cause performance issues with large datasets | Profile with production-sized data; optimize queries if needed |
| Conditional table formatting not visible in Streamlit | Use text formatting or custom HTML if native support is lacking |

---

## Success Criteria

✅ **All 8 improvements deployed and working:**
1. 7-day MA appears on Daily Sales Trend
2. APC chart Y-axis starts at 0
3. Weekday bars colored: green/red/gray
4. Category donut shows "Other" grouping, detail table shows all
5. KPI cards display period-over-period deltas
6. Drill-down expanders below each chart
7. Daily data table has conditional formatting + Indian numbers
8. Report tab shows previous-day deltas

✅ **Code quality:**
- All new functions have docstrings
- Unit tests cover utilities and table formatters (≥80% coverage)
- No linting errors (ruff check/format)
- Code follows AGENTS.md style guide (imports, naming, type hints)

✅ **Performance:**
- Charts render in <2s for typical 30-day periods
- Tables display in <1s
- No noticeable lag on multi-outlet views

✅ **User experience:**
- All improvements are discoverable (expanders labeled clearly)
- Drill-down data matches chart exactly
- Indian formatting is consistent across dashboard
- Conditional coloring is obvious (green=good, red=bad, yellow=warning)

---

## Timeline & Effort Estimate

| Task | Effort | Duration |
|------|--------|----------|
| Create `chart_builders.py` | 4–5 hours | 1 day |
| Create `table_formatters.py` | 3–4 hours | 1 day |
| Enhance `utils.py` | 2–3 hours | 0.5 day |
| Refactor `analytics_sections.py` | 2–3 hours | 0.5 day |
| Update `report_tab.py` | 1–2 hours | 0.25 day |
| Unit tests | 3–4 hours | 1 day |
| Integration testing | 2–3 hours | 0.5 day |
| Manual testing & bug fixes | 2–3 hours | 0.5 day |
| **Total** | **~22–27 hours** | **~5 days** |

---

## Notes & Assumptions

- **Streamlit native dataframe:** As of Streamlit 1.28+, `st.dataframe()` has limited conditional cell formatting. We may need to use HTML/CSS for advanced table styling, or rely on text formatting + Streamlit's native contrast.
- **Moving average calculation:** Uses existing `tabs/forecasting.py::moving_average()` function; no new algorithm needed.
- **Indian number format:** Custom implementation in `utils.py` to ensure consistent formatting across all currency displays.
- **Expanders:** Streamlit's expanders are lightweight and won't cause performance issues for typical data sizes.
- **Previous-day comparison:** Only shows if data exists for the previous day; graceful fallback if no data.

---

## Appendix: Example Outputs

### Indian Currency Format
```
130235      → ₹1,30,235
12345678    → ₹1,23,45,678
0           → ₹0
-45000      → -₹45,000
```

### Delta Format
```
Current: 150000, Prior: 120000  → "+₹30,000 (+25.0%)"  [green]
Current: 80000,  Prior: 100000  → "-₹20,000 (-20.0%)"  [red]
```

### Conditional Table Colors
```
Achievement: 120%   → Green background
Achievement: 85%    → Yellow background
Achievement: 45%    → Red background
```

---

**Spec Status:** ✅ **Ready for Implementation**

**Next Step:** Invoke `writing-plans` skill to create implementation plan.
