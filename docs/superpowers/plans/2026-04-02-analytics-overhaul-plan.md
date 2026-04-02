# Analytics Tab Overhaul Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign Analytics tab with themed sections, period-over-period chart comparisons, outlier highlighting, and KPI sparklines.

**Architecture:** Refactor analytics_tab.py into 4 collapsible themed sections (Overview, Sales Performance, Revenue Breakdown, Target Tracking). Add dual-line/dual-bar overlays on all charts comparing current vs prior period.

**Tech Stack:** Streamlit, Plotly, pandas, existing database.py queries

---

## File Structure

| File | Change | Purpose |
|------|--------|---------|
| `tabs/analytics_tab.py` | Modify | Refactor into themed sections, add comparison charts |
| `database.py` | Modify (if needed) | May need new query for sparkline data |
| `ui_theme.py` | No change | Use existing constants |
| `utils.py` | No change | Use existing helpers |

---

## Task 1: Prepare Prior-Period Data Helper

**Files:**
- Modify: `tabs/analytics_tab.py:62-78` (add prior_period_df as persistent attribute)

- [ ] **Step 1: Review current prior-period logic**

The existing code already calculates `prior_start` and `prior_end` at lines 62-78. It fetches `prior_summaries` at lines 109-116 but only uses it for KPI deltas.

```python
# Current prior fetching (lines 109-116 in analytics_tab.py):
prior_summaries = []
if prior_start and prior_end:
    prior_summaries = database.get_summaries_for_date_range_multi(
        ctx.report_loc_ids,
        prior_start.strftime("%Y-%m-%d"),
        prior_end.strftime("%Y-%m-%d"),
    )
prior_df = pd.DataFrame(prior_summaries) if prior_summaries else pd.DataFrame()
```

- [ ] **Step 2: Create helper function to merge current + prior for charts**

Add this helper at top of analytics_tab.py (after imports, before render function):

```python
def _merge_period_data(
    current_df: pd.DataFrame,
    prior_df: pd.DataFrame,
    date_col: str = "date",
    value_col: str = "net_total",
) -> pd.DataFrame:
    """Merge current and prior period data for dual-line chart comparison."""
    import pandas as pd
    
    if current_df.empty or prior_df.empty:
        return pd.DataFrame()
    
    current = current_df.copy()
    prior = prior_df.copy()
    
    # Add period label
    current["period"] = "Current"
    prior["period"] = "Prior"
    
    # Normalize dates to day-of-period for comparison
    current["day_num"] = range(1, len(current) + 1)
    prior["day_num"] = range(1, len(prior) + 1)
    
    # Concatenate
    merged = pd.concat([current, prior], ignore_index=True)
    return merged
```

- [ ] **Step 3: Commit**

```bash
git add tabs/analytics_tab.py
git commit -m "feat(analytics): add prior-period merge helper"
```

---

## Task 2: Create Themed Section Structure

**Files:**
- Modify: `tabs/analytics_tab.py:105-178` (refactor KPI section into Overview section)

- [ ] **Step 1: Wrap existing KPI section in collapsible container**

Current code at lines 127-178 creates KPIs without section wrapper. Replace with:

```python
# ── Section 1: Overview ───────────────────────────────────────────
with st.expander("📊 Overview", expanded=True):
    st.markdown("### Period Summary")
    with st.container(border=True):
        # ... existing KPI code (lines 127-177) ...
        
        # Add sparklines after each KPI (new)
        _sparkline_col1, _sparkline_col2, _sparkline_col3, _sparkline_col4 = st.columns(4)
        # Sparkline implementation in Task 5
```

- [ ] **Step 2: Create Sales Performance section wrapper**

After Overview section (around line 178), add:

```python
# ── Section 2: Sales Performance ─────────────────────────────────
with st.expander("💰 Sales Performance", expanded=True):
    # Charts will go here - Tasks 3 & 4
```

- [ ] **Step 3: Create Revenue Breakdown section wrapper**

After Sales Performance charts (around line 302), add:

```python
# ── Section 3: Revenue Breakdown ─────────────────────────────────
with st.expander("📈 Revenue Breakdown", expanded=True):
    # Charts will go here - Tasks 3 & 4
```

- [ ] **Step 4: Create Target Tracking section wrapper**

After Revenue Breakdown charts (around line 460), add:

```python
# ── Section 4: Target Tracking ───────────────────────────────────
with st.expander("🎯 Target Tracking", expanded=True):
    # Charts will go here - Tasks 3 & 4
```

- [ ] **Step 5: Commit**

```bash
git add tabs/analytics_tab.py
git commit -m "feat(analytics): add themed section wrappers"
```

---

## Task 3: Add Period Comparison to Sales Trend Chart

**Files:**
- Modify: `tabs/analytics_tab.py:184-210` (Daily Sales Trend chart)

- [ ] **Step 1: Modify Daily Sales Trend to show dual lines**

Current code at lines 184-210 creates single line chart. Replace with:

```python
with col_chart1:
    st.markdown("### Daily Sales Trend")
    
    if not df.empty:
        # Prepare data for dual-line comparison
        current_trend = df[["date", "net_total"]].copy()
        current_trend["period"] = "Current"
        
        if not prior_df.empty:
            prior_trend = prior_df[["date", "net_total"]].copy()
            prior_trend["period"] = "Prior"
            # Align dates to period day number
            current_trend["day_num"] = range(1, len(current_trend) + 1)
            prior_trend["day_num"] = range(1, len(prior_trend) + 1)
            
            combined = pd.concat([current_trend, prior_trend], ignore_index=True)
            
            fig_line = px.line(
                combined,
                x="day_num",
                y="net_total",
                color="period",
                markers=True,
                title="Net Sales: Current vs Prior Period",
                color_discrete_map={"Current": ui_theme.BRAND_PRIMARY, "Prior": "#94A3B8"},
            )
        else:
            fig_line = px.line(
                current_trend,
                x="date",
                y="net_total",
                markers=True,
                title="Net Sales Over Time",
            )
            fig_line.update_traces(line_color=ui_theme.BRAND_PRIMARY)
        
        fig_line.update_layout(
            xaxis_title="Day of Period",
            yaxis_title="Net Sales (₹)",
            hovermode="x unified",
            height=ui_theme.CHART_HEIGHT,
        )
        st.plotly_chart(fig_line, use_container_width=True)
        
        # Add best/worst day annotations
        if not df.empty and len(df) > 1:
            best_idx = df["net_total"].idxmax()
            worst_idx = df[df["net_total"] > 0]["net_total"].idxmin()
            best_val = df.loc[best_idx, "net_total"]
            worst_val = df.loc[worst_idx, "net_total"]
            best_date = df.loc[best_idx, "date"]
            worst_date = df.loc[worst_idx, "date"]
            
            fig_line.add_annotation(
                x=best_date, y=best_val,
                text="🏆 Best",
                showarrow=True, arrowhead=2,
                bgcolor=ui_theme.BRAND_SUCCESS,
            )
            fig_line.add_annotation(
                x=worst_date, y=worst_val,
                text="📉 Worst",
                showarrow=True, arrowhead=2,
                bgcolor=ui_theme.BRAND_ERROR,
            )
```

- [ ] **Step 2: Run Streamlit to verify chart renders**

Run: `streamlit run app.py` → Analytics tab → Verify chart appears with dual lines

- [ ] **Step 3: Commit**

```bash
git add tabs/analytics_tab.py
git commit -m "feat(analytics): add dual-line sales trend with annotations"
```

---

## Task 4: Add Prior-Period Comparison to Remaining Charts

**Files:**
- Modify: `tabs/analytics_tab.py:211-460` (covers, APC, payment, category, meal period, weekday charts)

- [ ] **Step 1: Add prior comparison to Covers Trend (col_chart2)**

Replace lines 211-231 with dual-bar comparison:

```python
with col_chart2:
    st.markdown("### Covers Trend")
    if not df.empty:
        current_covers = df[["date", "covers"]].copy()
        
        if not prior_df.empty:
            prior_covers = prior_df[["date", "covers"]].copy()
            current_covers["day_num"] = range(1, len(current_covers) + 1)
            prior_covers["day_num"] = range(1, len(prior_covers) + 1)
            current_covers["period"] = "Current"
            prior_covers["period"] = "Prior"
            
            combined_covers = pd.concat([current_covers, prior_covers], ignore_index=True)
            
            fig_bar = px.bar(
                combined_covers,
                x="day_num",
                y="covers",
                color="period",
                barmode="group",
                title="Covers: Current vs Prior",
                color_discrete_map={"Current": ui_theme.BRAND_SUCCESS, "Prior": "#94A3B8"},
            )
        else:
            fig_bar = px.bar(df, x="date", y="covers", title="Daily Covers")
            fig_bar.update_traces(marker_color=ui_theme.BRAND_SUCCESS)
        
        fig_bar.update_layout(
            xaxis_title="Day of Period",
            yaxis_title="Covers",
            height=ui_theme.CHART_HEIGHT,
        )
        st.plotly_chart(fig_bar, use_container_width=True)
```

- [ ] **Step 2: Add percentage labels to Payment Mode chart (lines 265-301)**

Replace current payment chart code with:

```python
# Payment totals calculation (existing)
payment_totals = {
    "Cash": float(df["cash_sales"].sum()),
    "GPay": float(df["gpay_sales"].sum()),
    "Zomato": float(df["zomato_sales"].sum()),
    "Card": float(df["card_sales"].sum()),
    "Other": float(df["other_sales"].sum()),
}

# Calculate prior period payment totals
prior_payment_totals = {}
if not prior_df.empty:
    prior_payment_totals = {
        "Cash": float(prior_df["cash_sales"].sum()),
        "GPay": float(prior_df["gpay_sales"].sum()),
        "Zomato": float(prior_df["zomato_sales"].sum()),
        "Card": float(prior_df["card_sales"].sum()),
        "Other": float(prior_df["other_sales"].sum()),
    }

# Create dataframe with both periods
pay_data = []
for mode, amount in payment_totals.items():
    prior_amount = prior_payment_totals.get(mode, 0)
    delta = amount - prior_amount
    delta_pct = (delta / prior_amount * 100) if prior_amount > 0 else None
    pay_data.append({
        "Mode": mode,
        "Amount": amount,
        "Prior": prior_amount,
        "Delta": delta,
        "DeltaPct": delta_pct,
    })
pay_df = pd.DataFrame(pay_data)

# Bar chart with labels
fig_pay = px.bar(
    pay_df,
    x="Amount",
    y="Mode",
    orientation="h",
    title="Payment mode split (₹)",
    text="Amount",
    color="Mode",
    color_discrete_map={
        "Cash": ui_theme.BRAND_PRIMARY,
        "GPay": "#0369a1",
        "Zomato": "#be185d",
        "Card": "#7c3aed",
        "Other": "#475569",
    },
)
fig_pay.update_traces(textposition="outside")
fig_pay.update_layout(
    xaxis_title="Amount (₹)",
    yaxis_title="",
    height=ui_theme.CHART_HEIGHT,
    showlegend=False,
)
st.plotly_chart(fig_pay, use_container_width=True)

# Show comparison table below
st.caption(f"Prior period: {utils.format_currency(float(prior_df['net_total'].sum()))}")
```

- [ ] **Step 3: Add % labels to Category pie chart (lines 333-344)**

Update pie chart with:

```python
fig_cat_pie = px.pie(
    cat_df,
    names="category",
    values="amount",
    title=f"Category revenue mix (Total: {utils.format_currency(cat_df['amount'].sum())})",
    hole=0.4,
    color="category",
    color_discrete_sequence=ui_theme.CHART_COLORWAY,
)
fig_cat_pie.update_traces(textposition="inside", textinfo="percent+label")
fig_cat_pie.update_layout(height=ui_theme.CHART_HEIGHT)
```

- [ ] **Step 4: Add prior comparison to Meal Period chart (lines 406-459)**

Add prior period data to meal period section:

```python
# Calculate service totals for prior period
prior_svc_totals = {}
if not prior_df.empty:
    prior_svc = database.get_service_sales_for_date_range(
        ctx.report_loc_ids,
        (start_date - timedelta(days=30)).strftime("%Y-%m-%d"),  # prior period
        (end_date - timedelta(days=30)).strftime("%Y-%m-%d"),
    )
    if prior_svc:
        prior_svc_df = pd.DataFrame(prior_svc)
        prior_svc_totals = prior_svc_df.set_index("service_type")["amount"].to_dict()
```

- [ ] **Step 5: Commit**

```bash
git add tabs/analytics_tab.py
git commit -m "feat(analytics): add prior comparison to remaining charts"
```

---

## Task 5: Add KPI Sparklines

**Files:**
- Modify: `tabs/analytics_tab.py:127-177` (KPI section within Overview)

- [ ] **Step 1: Create sparkline data fetching function**

Add at top of file after imports:

```python
def _get_sparkline_data(
    location_ids: List[int], days: int = 7
) -> pd.DataFrame:
    """Get last N days of sales for sparkline charts."""
    from datetime import datetime, timedelta
    
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=days - 1)
    
    summaries = database.get_summaries_for_date_range_multi(
        location_ids,
        start_date.strftime("%Y-%m-%d"),
        end_date.strftime("%Y-%m-%d"),
    )
    
    if summaries:
        return pd.DataFrame(summaries)
    return pd.DataFrame()
```

- [ ] **Step 2: Add sparkline after each KPI**

After each KPI metric, add a small line chart:

```python
# After Total Sales KPI (line 145):
spark_df = _get_sparkline_data(ctx.report_loc_ids, 7)
if not spark_df.empty:
    spark_fig = px.line(
        spark_df,
        x="date",
        y="net_total",
        markers=False,
    )
    spark_fig.update_layout(
        height=50,
        margin=dict(l=0, r=0, t=0, b=0),
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        paper_bgcolor="transparent",
        plot_bgcolor="transparent",
    )
    with kpi_cols[0]:
        st.plotly_chart(spark_fig, use_container_width=True, config={"displayModeBar": False})
```

- [ ] **Step 3: Commit**

```bash
git add tabs/analytics_tab.py
git commit -m "feat(analytics): add KPI sparklines"
```

---

## Task 6: Add Section Delta Headers

**Files:**
- Modify: `tabs/analytics_tab.py` (each section header)

- [ ] **Step 1: Calculate section-level deltas**

Add delta calculation before each section header:

```python
# Before Sales Performance section:
sales_delta = None
if prior_total and total_sales:
    sales_delta = utils.format_delta(total_sales, prior_total)

st.markdown(f"### 💰 Sales Performance {f'({sales_delta})' if sales_delta else ''}")
```

- [ ] **Step 2: Apply to all 4 sections**

Repeat for Revenue Breakdown (use category total) and Target Tracking (use target achievement).

- [ ] **Step 3: Commit**

```bash
git add tabs/analytics_tab.py
git commit -m "feat(analytics): add section delta headers"
```

---

## Task 7: Comprehensive Testing

**Files:**
- Test: Manual verification of all scenarios

- [ ] **Step 1: Test period selector with all options**

Run: `streamlit run app.py` → Analytics tab
- [ ] This Week
- [ ] Last Week
- [ ] Last 7 Days
- [ ] This Month
- [ ] Last Month
- [ ] Last 30 Days
- [ ] Custom

Verify each period shows correct date range in section headers.

- [ ] **Step 2: Test prior-period comparison**

Select "This Month" — verify prior period is "Last Month" and charts show dual lines.

- [ ] **Step 3: Test multi-outlet view**

If multiple locations, verify outlet selector works and comparison charts aggregate correctly.

- [ ] **Step 4: Test edge cases**

- Empty prior period (first month of data): Charts show single line, note says "No prior data"
- Single day data: Charts render but annotations don't show
- Zero sales days: Handled gracefully, worst day ignores zeros

- [ ] **Step 5: Commit**

```bash
git commit -m "test(analytics): verify all periods and edge cases"
```

---

## Summary

| Task | Changes |
|------|---------|
| 1 | Prior-period data helper |
| 2 | Themed section structure |
| 3 | Sales trend dual-line + annotations |
| 4 | Remaining charts comparison |
| 5 | KPI sparklines |
| 6 | Section delta headers |
| 7 | Testing |

**Plan complete.** Saved to `docs/superpowers/plans/2026-04-02-analytics-overhaul-plan.md`.

---

## Execution Choice

**Two options:**

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?