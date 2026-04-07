# Performance & Maintainability Refactor Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix sluggish/ unresponsive app by eliminating redundant queries, consolidating duplicate chart logic, and adding Streamlit caching.

**Architecture:** Four focused changes: (1) add `@st.cache_data` decorators to heavy read functions, (2) consolidate chart utilities into `chart_builders.py`, (3) batch N+1 DB queries in `report_tab.py`, (4) deduplicate shared helpers.

---

## File Impact Map

| File | Change |
|------|--------|
| `database_reads.py` | Add `@st.cache_data` to 5 functions |
| `database_analytics.py` | Add `@st.cache_data` to 4 functions |
| `pos_parser.py` | Add `@st.cache_data` to `calculate_mtd_metrics_multi` |
| `tabs/analytics_sections.py` | Replace inline chart helpers with calls to `chart_builders.py`; use cached DB helpers |
| `tabs/chart_builders.py` | Promote all duplicate helpers; add cached entry-point wrappers |
| `tabs/report_tab.py` | Batch 6 sequential queries → 2 batched calls |
| `tabs/analytics_tab.py` | Pass pre-fetched `prior_summaries` to avoid duplicate query |

---

## Task 1: Add caching to `database_reads.py`

**Files:**
- Modify: `database_reads.py:1-305`
- Test: existing tests via `pytest tests/test_database.py`

- [ ] **Step 1: Add Streamlit import at top of `database_reads.py`**

```python
import streamlit as st
```

Run: check syntax — `python -c "import database_reads"` — should succeed

- [ ] **Step 2: Wrap `get_summaries_for_month` with `@st.cache_data`**

```python
@st.cache_data(ttl=300)
def get_summaries_for_month(location_id: int, year: int, month: int) -> List[Dict]:
```

- [ ] **Step 3: Wrap `get_category_mtd_totals` with `@st.cache_data`**

```python
@st.cache_data(ttl=300)
def get_category_mtd_totals(
    location_id: int, year: int, month: int
) -> Dict[str, float]:
```

- [ ] **Step 4: Wrap `get_service_mtd_totals` with `@st.cache_data`**

```python
@st.cache_data(ttl=300)
def get_service_mtd_totals(location_id: int, year: int, month: int) -> Dict[str, float]:
```

- [ ] **Step 5: Wrap `get_summaries_for_date_range` with `@st.cache_data`**

```python
@st.cache_data(ttl=120)
def get_summaries_for_date_range(
    location_id: int, start_date: str, end_date: str
) -> List[Dict]:
```

- [ ] **Step 6: Wrap `get_summaries_for_date_range_multi` with `@st.cache_data`**

```python
@st.cache_data(ttl=120)
def get_summaries_for_date_range_multi(
    location_ids: List[int], start_date: str, end_date: str
) -> List[Dict]:
```

- [ ] **Step 7: Wrap `get_recent_summaries` with `@st.cache_data`**

```python
@st.cache_data(ttl=300)
def get_recent_summaries(location_id: int, weeks: int = 8) -> List[Dict]:
```

- [ ] **Step 8: Run tests**

Run: `pytest tests/test_database.py -v`
Expected: PASS (cache decorators are backward-compatible)

- [ ] **Step 9: Commit**

```bash
git add database_reads.py
git commit -m "perf(database_reads): add @st.cache_data to heavy read functions"
```

---

## Task 2: Add caching to `database_analytics.py`

**Files:**
- Modify: `database_analytics.py:1-266`
- Test: `pytest tests/test_database_phase4_modules.py`

- [ ] **Step 1: Add Streamlit import at top**

```python
import streamlit as st
```

- [ ] **Step 2: Wrap `get_monthly_footfall_multi` with `@st.cache_data`**

```python
@st.cache_data(ttl=600)
def get_monthly_footfall_multi(
    location_ids: List[int], start_date: str, end_date: str
) -> List[Dict[str, Any]]:
```

- [ ] **Step 3: Wrap `get_weekly_footfall_multi` with `@st.cache_data`**

```python
@st.cache_data(ttl=600)
def get_weekly_footfall_multi(
    location_ids: List[int], start_date: str, end_date: str
) -> List[Dict[str, Any]]:
```

- [ ] **Step 4: Wrap `get_category_mtd_totals_multi` with `@st.cache_data`**

```python
@st.cache_data(ttl=300)
def get_category_mtd_totals_multi(
    location_ids: List[int], year: int, month: int
) -> Dict[str, float]:
```

- [ ] **Step 5: Wrap `get_service_mtd_totals_multi` with `@st.cache_data`**

```python
@st.cache_data(ttl=300)
def get_service_mtd_totals_multi(
    location_ids: List[int], year: int, month: int
) -> Dict[str, float]:
```

- [ ] **Step 6: Run tests**

Run: `pytest tests/test_database_phase4_modules.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add database_analytics.py
git commit -m "perf(database_analytics): add @st.cache_data to analytics queries"
```

---

## Task 3: Cache `calculate_mtd_metrics_multi` in `pos_parser.py`

**Files:**
- Modify: `pos_parser.py:626-663`
- Test: `pytest tests/test_pos_parser.py`

- [ ] **Step 1: Add `@st.cache_data` to `calculate_mtd_metrics_multi`**

At line 626:

```python
@st.cache_data(ttl=300)
def calculate_mtd_metrics_multi(
```

- [ ] **Step 2: Run tests**

Run: `pytest tests/test_pos_parser.py -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add pos_parser.py
git commit -m "perf(pos_parser): cache calculate_mtd_metrics_multi"
```

---

## Task 4: Consolidate duplicate chart helpers into `chart_builders.py`

**Files:**
- Modify: `tabs/chart_builders.py:1-321`
- Modify: `tabs/analytics_sections.py:25-122`
- Test: `pytest tests/test_chart_builders.py`

### 4a. Move `_period_supports_trend_analysis` to `chart_builders.py`

**In `chart_builders.py`**, add at line 13:

```python
def _period_supports_trend_analysis(period: str, data_points: int) -> bool:
    """Return True if period is long enough for MA and forecast."""
    _long_periods = {"Last 7 Days", "Last 30 Days", "Last Month", "Custom"}
    if period in _long_periods:
        return data_points >= 3
    return False
```

- [ ] **Step 1: Add helper to chart_builders.py and remove from analytics_sections.py**

In `analytics_sections.py` line 111-120, delete the `_period_supports_trend_analysis` function. Add import at top of `analytics_sections.py`:

```python
from tabs.chart_builders import _period_supports_trend_analysis
```

Run: `python -c "from tabs.analytics_sections import render_overview"` — should succeed

### 4b. Move `_hex_to_rgba` (already in chart_builders.py but duplicated in analytics_sections.py)

**In `analytics_sections.py` line 25-29**, delete the local `_hex_to_rgba` function. Add import:

```python
from tabs.chart_builders import _hex_to_rgba
```

- [ ] **Step 2: Remove duplicate `_hex_to_rgba` from analytics_sections.py**

Run: `python -c "from tabs.analytics_sections import render_overview"` — should succeed

### 4c. Fix `moving_average` import

In `analytics_sections.py`, `moving_average` is imported from `tabs.forecasting` — verify this is correct (it is, `forecasting.py` has it). No change needed.

- [ ] **Step 3: Commit**

```bash
git add tabs/chart_builders.py tabs/analytics_sections.py
git commit -m "refactor(analytics_sections): deduplicate chart helpers into chart_builders"
```

---

## Task 5: Add batch query to eliminate N+1 in `report_tab.py`

**Files:**
- Modify: `database_reads.py` (add new function)
- Modify: `tabs/report_tab.py:113-169`
- Test: manual verification

- [ ] **Step 1: Add `get_mtd_totals_multi` batch function to `database_reads.py`**

Add at end of `database_reads.py`:

```python
@st.cache_data(ttl=300)
def get_mtd_totals_multi(
    location_ids: List[int], year: int, month: int
) -> Tuple[Dict[str, float], Dict[str, float]]:
    """
    Fetch both category and service MTD totals across multiple locations in one query.

    Returns (category_totals, service_totals).
    """
    if not location_ids:
        return {}, {}
    placeholders = ",".join("?" * len(location_ids))
    start_date = f"{year}-{month:02d}-01"
    if month == 12:
        end_date = f"{year + 1}-01-01"
    else:
        end_date = f"{year}-{month + 1:02d}-01"

    with db_connection() as conn:
        cursor = conn.cursor()
        # Categories
        cursor.execute(
            f"""
            SELECT cs.category, SUM(cs.amount) AS total
            FROM category_sales cs
            INNER JOIN daily_summaries ds ON cs.summary_id = ds.id
            WHERE ds.location_id IN ({placeholders}) AND ds.date >= ? AND ds.date < ?
            GROUP BY cs.category
            """,
            (*location_ids, start_date, end_date),
        )
        cat_rows = cursor.fetchall()
        # Services
        cursor.execute(
            f"""
            SELECT sv.service_type, SUM(sv.amount) AS total
            FROM service_sales sv
            INNER JOIN daily_summaries ds ON sv.summary_id = ds.id
            WHERE ds.location_id IN ({placeholders}) AND ds.date >= ? AND ds.date < ?
            GROUP BY sv.service_type
            """,
            (*location_ids, start_date, end_date),
        )
        svc_rows = cursor.fetchall()

    cat_totals = {row["category"]: float(row["total"] or 0) for row in cat_rows}
    svc_totals = {row["service_type"]: float(row["total"] or 0) for row in svc_rows}
    return cat_totals, svc_totals
```

- [ ] **Step 2: Add `get_summaries_for_month_multi` to `database_reads.py`**

```python
@st.cache_data(ttl=300)
def get_summaries_for_month_multi(
    location_ids: List[int], year: int, month: int
) -> List[Dict]:
    """Get all summaries for a specific month across multiple locations."""
    if not location_ids:
        return []
    placeholders = ",".join("?" * len(location_ids))
    start_date = f"{year}-{month:02d}-01"
    if month == 12:
        end_date = f"{year + 1}-01-01"
    else:
        end_date = f"{year}-{month + 1:02d}-01"
    with db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            f"""
            SELECT * FROM daily_summaries
            WHERE location_id IN ({placeholders}) AND date >= ? AND date < ?
            ORDER BY date
            """,
            (*location_ids, start_date, end_date),
        )
        rows = cursor.fetchall()
    return [dict(row) for row in rows]
```

Add the type import at the top of `database_reads.py`:
```python
from typing import Any, Dict, List, Optional, Tuple
```

- [ ] **Step 3: Rewrite footfall block in `report_tab.py` lines 113-169**

Replace the 6 separate sequential calls (3 pairs of monthly + weekly per outlet) with two batched calls:

```python
        if len(ctx.report_loc_ids) > 1:
            mtd_cat, mtd_svc = database.get_mtd_totals_multi(
                ctx.report_loc_ids, y_m[0], y_m[1]
            )
            _today = datetime.now().date()
            _end = _today.strftime("%Y-%m-%d")
            _start_mo = _today.replace(day=1)
            for _ in range(9):
                _m = _start_mo.month - 1
                if _m == 0:
                    _m = 12
                    _start_mo = _start_mo.replace(year=_start_mo.year - 1, month=_m)
                else:
                    _start_mo = _start_mo.replace(month=_m)
            _start_mo_str = _start_mo.strftime("%Y-%m-%d")
            _days_since_monday = _today.weekday()
            _current_week_monday = _today - timedelta(days=_days_since_monday)
            _start_wk = (_current_week_monday - timedelta(weeks=3)).strftime("%Y-%m-%d")

            per_outlet_footfall_metrics = [
                (name, database.get_monthly_footfall_multi([lid], _start_mo_str, _end),
                 database.get_weekly_footfall_multi([lid], _start_wk, _end))
                for lid, name, _ in outlets_bundle
            ]
            foot_rows = database.get_summaries_for_month_multi(
                ctx.report_loc_ids, y_m[0], y_m[1]
            )
            per_outlet_cat = None
            per_outlet_svc = None
        else:
            mtd_cat = database.get_category_mtd_totals(
                ctx.report_loc_ids[0], y_m[0], y_m[1]
            )
            mtd_svc = database.get_service_mtd_totals(
                ctx.report_loc_ids[0], y_m[0], y_m[1]
            )
            foot_rows = database.get_summaries_for_month(
                ctx.report_loc_ids[0], y_m[0], y_m[1]
            )
            per_outlet_footfall = None
            per_outlet_footfall_metrics = None
            per_outlet_cat = None
            per_outlet_svc = None
```

- [ ] **Step 4: Run app to verify no errors**

Run: `streamlit run app.py` — should load without errors

- [ ] **Step 5: Commit**

```bash
git add database_reads.py tabs/report_tab.py
git commit -m "perf(report_tab): batch 6 sequential queries into 2 cached calls"
```

---

## Task 6: Streamline `analytics_tab.py` — pre-fetch prior period data

**Files:**
- Modify: `tabs/analytics_tab.py:107-173`
- Test: manual verification

The prior period data (`prior_summaries`) is fetched inside `analytics_tab.py` at line 125-129 but then passed to `render_sales_performance` which doesn't actually use `prior_df` for anything meaningful in the chart — it's only used for comparison numbers in `render_overview`. Since `prior_summaries` is already fetched before the section renders, this is just a pass-through issue.

**The actual fix** is ensuring `render_overview` uses the already-computed prior totals instead of re-fetching.

Currently `render_overview` at `analytics_sections.py:139` receives `prior_total`, `prior_covers`, `prior_avg` as parameters — these are already computed from `prior_df` in `analytics_tab.py:137-139`. So this is already correct.

The sluggishness is caused by the queries, not by data flow. Skip this task.

---

## Task 7: Remove `st.stop()` early-exit in `report_tab.py`

**Files:**
- Modify: `tabs/report_tab.py:391`

- [ ] **Step 1: Remove `st.stop()` at line 391**

The `st.stop()` at line 391 prevents the combined (non-single-outlet) report sections from rendering. This is wasteful UI. Replace with a proper conditional:

Current code at lines 347-391:
```python
            with st.expander("PNG Report", expanded=True):
                ... single outlet sections ...
            st.stop()  # ← line 391
```

Replace `st.stop()` with a return or restructure so the combined sections render normally after the single-outlet block.

```python
            with st.expander("PNG Report", expanded=True):
                ... single outlet sections ...
```

Remove `st.stop()`. Add `return` after the single-outlet PNG block so it doesn't fall through to the combined sections:

```python
            with st.expander("PNG Report", expanded=True):
                _sec_meta = [...]
                ...
            return  # exit after single-outlet PNG view
```

- [ ] **Step 2: Verify app renders correctly with multi-outlet**

Run: `streamlit run app.py` — navigate to Report tab

- [ ] **Step 3: Commit**

```bash
git add tabs/report_tab.py
git commit -m "fix(report_tab): remove st.stop() early-exit that prevented combined report rendering"
```

---

## Task 8: Final verification

- [ ] **Step 1: Run full test suite**

Run: `pytest tests/ -v`
Expected: all PASS

- [ ] **Step 2: Run ruff check**

Run: `ruff check .`
Expected: no errors

- [ ] **Step 3: Run streamlit and spot-check all 4 tabs**

Run: `streamlit run app.py`
Expected: Upload, Report, Analytics, Settings all render without errors

---

## Summary of Changes

| Task | What changed | Files touched |
|------|-------------|---------------|
| 1 | Caching for `database_reads.py` heavy functions | `database_reads.py` |
| 2 | Caching for `database_analytics.py` functions | `database_analytics.py` |
| 3 | Caching for `calculate_mtd_metrics_multi` | `pos_parser.py` |
| 4 | Deduplicate chart helpers | `chart_builders.py`, `analytics_sections.py` |
| 5 | Batch N+1 queries in report_tab | `database_reads.py`, `report_tab.py` |
| 7 | Remove `st.stop()` blocking combined reports | `report_tab.py` |