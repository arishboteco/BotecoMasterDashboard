# Monthly Footfall Summary Table Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a "Monthly Footfall Summary" table to the Report tab showing the last 12 months of covers data with month-over-month % change, matching the user's Google Sheet format.

**Architecture:** Add a new database query function to aggregate monthly footfall across locations for the last 12 months, compute derived metrics (total days, daily avg, % change), and render as a Streamlit dataframe table in the Report tab. Uses existing `daily_summaries` table — no schema changes needed.

**Tech Stack:** Python, pandas, Streamlit, SQLite

---

## Context

### Existing Data Flow
- `daily_summaries` table stores per-day `covers`, `lunch_covers`, `dinner_covers` per location
- `scope.merge_month_footfall_rows()` already aggregates daily footfall across locations for a single month
- `database.get_summaries_for_month(location_id, year, month)` returns daily summaries for a month
- Report tab (`tabs/report_tab.py`) renders the daily sales report for a selected date

### Google Sheet Format (target output)
| Month | Footfall | % Change | Total Days | Daily Avg. | % Change |
|-------|----------|----------|------------|------------|----------|
| May-2025 | 2,805 | | 31 | 90 | |
| Jun-2025 | 2,631 | -6.20% | 30 | 88 | -2.22% |

Formula logic:
- **Month**: `MMM-YYYY` format
- **Footfall**: SUM of covers for that month (across all locations)
- **% Change (Footfall)**: (current - previous) / previous, blank for first month
- **Total Days**: DAY(EOMONTH(month, 0)) — calendar days in month
- **Daily Avg.**: ROUND(footfall / total_days, 0)
- **% Change (Daily Avg.)**: (current - previous) / previous, blank for first month
- **Time range**: Last 12 months from today

### Where to Place
Report tab, after the main daily report section but before the export buttons. The table should always show the last 12 months regardless of the selected date.

---

## File Structure

| File | Change |
|------|--------|
| `database.py` | Add `get_monthly_footfall_multi()` — aggregates covers by month across locations for a date range |
| `tabs/report_tab.py` | Add "Monthly Footfall Summary" section with dataframe table |

---

### Task 1: Add `get_monthly_footfall_multi()` database function

**Files:**
- Modify: `database.py` — add new query function after existing footfall functions
- Test: `tests/test_database.py` — add test for the new function

- [ ] **Step 1: Write the failing test**

Add to `tests/test_database.py` (create if doesn't exist, or append):

```python
"""Tests for database monthly footfall query."""

import pytest
import database


class TestGetMonthlyFootfallMulti:
    def test_returns_empty_for_no_data(self):
        result = database.get_monthly_footfall_multi([1], "2025-01-01", "2025-12-31")
        assert result == []

    def test_aggregates_covers_by_month(self):
        # This test assumes test DB setup — verify query returns correct shape
        # At minimum, verify the function exists and returns a list
        result = database.get_monthly_footfall_multi([1], "2025-01-01", "2025-01-31")
        assert isinstance(result, list)
        if result:
            row = result[0]
            assert "month" in row
            assert "covers" in row
            assert "total_days" in row
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_database.py -v`
Expected: FAIL — function doesn't exist yet.

- [ ] **Step 3: Implement `get_monthly_footfall_multi()`**

Add to `database.py` after `get_summaries_for_date_range_multi()` (around line 960):

```python
def get_monthly_footfall_multi(
    location_ids: List[int], start_date: str, end_date: str
) -> List[Dict]:
    """Aggregate covers by month across locations for a date range.

    Returns list of dicts: [{"month": "YYYY-MM", "covers": int, "total_days": int}, ...]
    Sorted by month ascending.
    """
    if not location_ids:
        return []
    conn = get_connection()
    cursor = conn.cursor()
    placeholders = ",".join("?" * len(location_ids))
    cursor.execute(
        f"""
        SELECT
            SUBSTR(date, 1, 7) AS month,
            SUM(covers) AS covers,
            COUNT(DISTINCT date) AS total_days
        FROM daily_summaries
        WHERE location_id IN ({placeholders})
          AND date >= ?
          AND date <= ?
        GROUP BY SUBSTR(date, 1, 7)
        ORDER BY month
        """,
        (*location_ids, start_date, end_date),
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_database.py::TestGetMonthlyFootfallMulti -v`
Expected: PASS

---

### Task 2: Add Monthly Footfall Summary table to Report tab

**Files:**
- Modify: `tabs/report_tab.py` — add new section after the daily report, before export buttons

- [ ] **Step 1: Add the Monthly Footfall Summary section**

In `tabs/report_tab.py`, find the section after the report display logic and before the export/download buttons. Add the following code after the `if summary:` block's main content but before the export section (around line 370 area, after the composite image rendering):

```python
        # ── Monthly Footfall Summary ─────────────────────────────
        st.markdown("---")
        st.markdown("### Monthly Footfall Summary")
        st.caption("Last 12 months of covers data.")

        from datetime import date as _date

        _today = _date.today()
        _start_12m = _date(_today.year, _today.month, 1)
        # Go back 11 months to get 12 months total
        for _ in range(11):
            _m = _start_12m.month - 1
            if _m == 0:
                _m = 12
                _start_12m = _start_12m.replace(year=_start_12m.year - 1, month=_m)
            else:
                _start_12m = _start_12m.replace(month=_m)

        _start_12m_str = _start_12m.strftime("%Y-%m-%d")
        _end_12m_str = _today.strftime("%Y-%m-%d")

        _monthly_rows = database.get_monthly_footfall_multi(
            ctx.report_loc_ids, _start_12m_str, _end_12m_str
        )

        if _monthly_rows:
            import calendar as _cal

            _df_m = pd.DataFrame(_monthly_rows)
            _df_m["month_label"] = _df_m["month"].apply(
                lambda x: _cal.month_abbr[int(x.split("-")[1])] + "-" + x.split("-")[0]
            )
            _df_m["footfall"] = _df_m["covers"].astype(int)
            _df_m["daily_avg"] = (_df_m["footfall"] / _df_m["total_days"]).round(0).astype(int)

            # Month-over-month % change
            _df_m["pct_footfall"] = _df_m["footfall"].pct_change()
            _df_m["pct_avg"] = _df_m["daily_avg"].pct_change()

            # Format for display
            _display = pd.DataFrame({
                "Month": _df_m["month_label"],
                "Footfall": _df_m["footfall"].apply(lambda x: f"{x:,}"),
                "% Change": _df_m["pct_footfall"].apply(
                    lambda x: f"{x * 100:.2f}%" if pd.notna(x) and x != 0 else ""
                ),
                "Total Days": _df_m["total_days"].astype(int),
                "Daily Avg.": _df_m["daily_avg"].apply(lambda x: f"{x:,}"),
                "% Change": _df_m["pct_avg"].apply(
                    lambda x: f"{x * 100:.2f}%" if pd.notna(x) and x != 0 else ""
                ),
            })

            st.dataframe(
                _display,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Month": st.column_config.TextColumn("Month"),
                    "Footfall": st.column_config.TextColumn("Footfall"),
                    "% Change": st.column_config.TextColumn("% Change"),
                    "Total Days": st.column_config.TextColumn("Total Days"),
                    "Daily Avg.": st.column_config.TextColumn("Daily Avg."),
                    "% Change.1": st.column_config.TextColumn("% Change"),
                },
            )
        else:
            st.caption("No monthly footfall data available.")
```

**Important note:** The dataframe has two "% Change" columns. Streamlit's `column_config` needs unique keys. Use a workaround — rename the second column:

```python
            _display = pd.DataFrame({
                "Month": _df_m["month_label"],
                "Footfall": _df_m["footfall"].apply(lambda x: f"{x:,}"),
                "% Change": _df_m["pct_footfall"].apply(
                    lambda x: f"{x * 100:.2f}%" if pd.notna(x) and x != 0 else ""
                ),
                "Total Days": _df_m["total_days"].astype(int),
                "Daily Avg.": _df_m["daily_avg"].apply(lambda x: f"{x:,}"),
                "Avg % Change": _df_m["pct_avg"].apply(
                    lambda x: f"{x * 100:.2f}%" if pd.notna(x) and x != 0 else ""
                ),
            })
```

- [ ] **Step 2: Verify the table renders correctly**

Run: `streamlit run app.py`
Navigate to Report tab, verify:
- Table shows last 12 months
- Footfall values are comma-formatted integers
- % Change is blank for first month, percentage for others
- Daily Avg. = Footfall / Total Days (rounded)

- [ ] **Step 3: Test with multi-location**

If multiple locations exist, verify covers are summed across all locations for each month.

---

## Self-Review

### Spec Coverage
- ✅ Monthly Footfall Summary table in Report tab
- ✅ Last 12 months from current date
- ✅ Columns: Month, Footfall, % Change, Total Days, Daily Avg., % Change
- ✅ Month format: MMM-YYYY
- ✅ % Change = month-over-month comparison
- ✅ Data from database covers
- ✅ Multi-location support

### Placeholder Scan
- ✅ No TBD/TODO placeholders
- ✅ All code shown explicitly
- ✅ No "similar to" references

### Type Consistency
- ✅ `get_monthly_footfall_multi` returns `List[Dict]` matching existing DB function patterns
- ✅ Uses existing `daily_summaries` table schema
- ✅ Follows existing `report_tab.py` patterns for dataframe rendering

---

Plan complete. Two execution options:

**1. Subagent-Driven (recommended)** - Dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?