# Standardize Date Selectors — Design

**Date:** 2026-04-07  
**Status:** Approved  
**Owner:** BotecoMasterDashboard

---

## Context

The app has inconsistent date selection patterns across tabs:

| Tab | Pattern |
|-----|---------|
| `report_tab.py` | Custom prev/next nav + inline `date_input` (duplicates `navigation.py` logic) |
| `analytics_tab.py` | Period selectbox + custom date range with two standalone `date_input` fields |
| `settings_tab.py` | Two standalone `date_input` fields for export date range |
| `components/navigation.py` | Reusable `date_nav()` component — exported but unused anywhere |

Problems: code duplication in `report_tab.py`, inconsistent UX across tabs, and no shared date-range component for multi-date selection.

---

## Design

### Components

#### `date_nav(session_key, label, help_text)` — existing, refactor

- 3-column layout: Prev button | date display | Next button
- `st.date_input` below the nav row
- Prev/Next buttons step by 1 day and call `st.rerun()`
- Date picker updates session state and calls `st.rerun()` on change
- Styled via `class="date-display"` HTML div

**Changes:**
- Add `format="DD/MM/YYYY"` to the `date_input` call for consistency

#### `date_range_nav(session_key_start, session_key_end, label_start, label_end)` — new

- Two `st.date_input` fields side by side (From / To) using `st.columns([1, 1])`
- Default start: today minus 29 days; default end: today
- Validates: if start > end, show a `st.warning` and return without rerunning
- Returns `(start_date, end_date)` as a tuple
- Both inputs use `format="DD/MM/YYYY"` for consistency

---

## Implementation

### 1. Refactor `components/navigation.py`

**`date_nav()` changes:**
- Add `format="DD/MM/YYYY"` to `st.date_input`

**`date_range_nav()` additions:**
- Import `date` from datetime or use `datetime.now().date()` for defaults
- Accept `session_key_start`, `session_key_end`, `label_start`, `label_end`
- Initialize session keys with defaults if not present
- Side-by-side layout with validation

### 2. Update `tabs/report_tab.py`

Remove inline nav code (lines ~35–63), replace with:

```python
selected_date = date_nav(
    session_key="report_date",
    label="Select a date",
    help_text="Choose a date to view that day's report",
)
```

Also remove the now-unused `from datetime import timedelta` if it was only for the nav.

### 3. Update `tabs/analytics_tab.py`

Replace custom date range inputs (currently `st.date_input` x2) with:

```python
custom_start, custom_end = date_range_nav(
    session_key_start="analytics_custom_start",
    session_key_end="analytics_custom_end",
    label_start="From",
    label_end="To",
)
```

Keep the period `selectbox` as-is. Keep the plain-text date range display.

### 4. Update `tabs/settings_tab.py`

Replace two standalone `date_input` calls with:

```python
exp_start, exp_end = date_range_nav(
    session_key_start="export_start",
    session_key_end="export_end",
    label_start="From date",
    label_end="To date",
)
```

Keep defaults as-is (start = first of month, end = today).

---

## Error Handling

- `date_range_nav`: if `start > end`, warn inline and return current values without state change or rerun
- `date_nav`: existing behavior unchanged — Streamlit handles invalid date input natively

---

## Files Affected

| File | Change |
|------|--------|
| `components/navigation.py` | Refactor `date_nav()` + add `date_range_nav()` |
| `tabs/report_tab.py` | Replace inline nav with `date_nav()` call |
| `tabs/analytics_tab.py` | Replace custom range inputs with `date_range_nav()` |
| `tabs/settings_tab.py` | Replace standalone inputs with `date_range_nav()` |

---

## Success Criteria

- `report_tab.py` no longer duplicates `navigation.py` logic
- All date inputs use `DD/MM/YYYY` format
- Date range selector is available as a reusable component
- Analytics retains period selectbox UX (correct for trend analysis)
- Settings export date range uses consistent component
