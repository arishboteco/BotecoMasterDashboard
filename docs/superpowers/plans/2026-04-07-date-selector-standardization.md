# Date Selector Standardization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Standardize all date selectors across the app by refactoring `components/navigation.py` and updating three tabs to use shared components.

**Architecture:** Add `date_range_nav()` to `components/navigation.py`, refactor `date_nav()` for consistent formatting, then update `report_tab.py`, `analytics_tab.py`, and `settings_tab.py` to use the shared components.

**Tech Stack:** Python, Streamlit, pytest

---

## File Map

| File | Change |
|------|--------|
| `components/navigation.py` | Refactor `date_nav()` + add `date_range_nav()` |
| `tabs/report_tab.py` | Replace inline nav with `date_nav()` call |
| `tabs/analytics_tab.py` | Replace custom range inputs with `date_range_nav()` |
| `tabs/settings_tab.py` | Replace standalone inputs with `date_range_nav()` |

---

## Tasks

### Task 1: Refactor `date_nav()` in `components/navigation.py`

**Files:**
- Modify: `components/navigation.py:41`

- [ ] **Step 1: Read the current `date_nav()` implementation**

Run: Read `components/navigation.py`

- [ ] **Step 2: Add `format="DD/MM/YYYY"` to the `st.date_input` call**

Edit `components/navigation.py` line 41–46, change:
```python
    picked = st.date_input(
        label,
        value=selected_date,
        key=f"{session_key}_picker",
        help=help_text,
    )
```
to:
```python
    picked = st.date_input(
        label,
        value=selected_date,
        key=f"{session_key}_picker",
        help=help_text,
        format="DD/MM/YYYY",
    )
```

- [ ] **Step 3: Commit**

```bash
git add components/navigation.py
git commit -m "refactor: add DD/MM/YYYY format to date_nav date_input"
```

---

### Task 2: Add `date_range_nav()` to `components/navigation.py`

**Files:**
- Modify: `components/navigation.py`

- [ ] **Step 1: Add `date_range_nav()` function after `date_nav()`**

Read the end of `components/navigation.py` to find where to append.

Add this function after the closing of `date_nav()`:

```python
def date_range_nav(
    session_key_start: str,
    session_key_end: str,
    label_start: str = "From",
    label_end: str = "To",
) -> tuple[datetime.date, datetime.date]:
    """Render a side-by-side date range selector (From / To) with validation."""
    today = datetime.now().date()

    if session_key_start not in st.session_state:
        st.session_state[session_key_start] = today - timedelta(days=29)
    if session_key_end not in st.session_state:
        st.session_state[session_key_end] = today

    col_start, col_end = st.columns(2)
    with col_start:
        start_date = st.date_input(
            label_start,
            value=st.session_state[session_key_start],
            key=session_key_start,
            format="DD/MM/YYYY",
        )
    with col_end:
        end_date = st.date_input(
            label_end,
            value=st.session_state[session_key_end],
            key=session_key_end,
            format="DD/MM/YYYY",
        )

    if start_date > end_date:
        st.warning(f"Start date ({start_date.strftime('%d/%m/%Y')}) cannot be after end date ({end_date.strftime('%d/%m/%Y')}).")
        return st.session_state.get(session_key_start, start_date), st.session_state.get(session_key_end, end_date)

    st.session_state[session_key_start] = start_date
    st.session_state[session_key_end] = end_date
    return start_date, end_date
```

- [ ] **Step 2: Update `components/__init__.py` to export `date_range_nav`**

Run: Read `components/__init__.py`

Add `date_range_nav` to the exports alongside `date_nav`.

- [ ] **Step 3: Commit**

```bash
git add components/navigation.py components/__init__.py
git commit -m "feat: add date_range_nav component for From/To date selection"
```

---

### Task 3: Update `report_tab.py` to use `date_nav()`

**Files:**
- Modify: `tabs/report_tab.py:35-63`

- [ ] **Step 1: Read the current inline nav implementation**

Run: Read `tabs/report_tab.py` lines 35–65

- [ ] **Step 2: Remove inline nav and replace with `date_nav()` call**

Remove lines 35–63 (the `selected_date` assignment through the `Next` button block).

Replace the removed block with:
```python
    selected_date = date_nav(
        session_key="report_date",
        label="Select a date",
        help_text="Choose a date to view that day's report",
    )
```

- [ ] **Step 3: Add import for `date_nav` if not present**

Run: Read top of `tabs/report_tab.py` imports

If `date_nav` is not imported from `components`, add:
```python
from components.navigation import date_nav
```

- [ ] **Step 4: Remove unused `from datetime import timedelta` import if present**

If `timedelta` is only used by the removed nav buttons, remove it from the imports.

- [ ] **Step 5: Verify the file runs**

Run: `python -c "import tabs.report_tab"` — no output means success.

- [ ] **Step 6: Commit**

```bash
git add tabs/report_tab.py
git commit -m "refactor: replace inline date nav with date_nav() component"
```

---

### Task 4: Update `analytics_tab.py` to use `date_range_nav()`

**Files:**
- Modify: `tabs/analytics_tab.py:47-63`

- [ ] **Step 1: Read the custom date range section**

Run: Read `tabs/analytics_tab.py` lines 47–68

- [ ] **Step 2: Replace the two `st.date_input` calls with `date_range_nav()`**

Remove:
```python
    custom_start = None
    custom_end = None
    if analysis_period == "Custom":
        with col_per2:
            c1, c2 = st.columns(2)
            with c1:
                custom_start = st.date_input(
                    "From",
                    datetime.now().date() - timedelta(days=29),
                    key="analytics_custom_start",
                )
            with c2:
                custom_end = st.date_input(
                    "To",
                    datetime.now().date(),
                    key="analytics_custom_end",
                )
```

Replace with:
```python
    custom_start = None
    custom_end = None
    if analysis_period == "Custom":
        with col_per2:
            custom_start, custom_end = date_range_nav(
                session_key_start="analytics_custom_start",
                session_key_end="analytics_custom_end",
                label_start="From",
                label_end="To",
            )
```

- [ ] **Step 3: Add import for `date_range_nav` if not present**

Run: Read top of `tabs/analytics_tab.py` imports

If `date_range_nav` is not imported from `components`, add:
```python
from components.navigation import date_range_nav
```

- [ ] **Step 4: Verify the file runs**

Run: `python -c "import tabs.analytics_tab"` — no output means success.

- [ ] **Step 5: Commit**

```bash
git add tabs/analytics_tab.py
git commit -m "refactor: replace inline date range inputs with date_range_nav()"
```

---

### Task 5: Update `settings_tab.py` to use `date_range_nav()`

**Files:**
- Modify: `tabs/settings_tab.py:361-372`

- [ ] **Step 1: Read the export date inputs section**

Run: Read `tabs/settings_tab.py` lines 361–375

- [ ] **Step 2: Replace the two `st.date_input` calls with `date_range_nav()`**

Remove:
```python
    with exp_c2:
        exp_start = st.date_input(
            "From date",
            value=datetime.now().date().replace(day=1),
            key="export_start",
        )
    with exp_c3:
        exp_end = st.date_input(
            "To date",
            value=datetime.now().date(),
            key="export_end",
        )
```

Replace with a single call using the existing `exp_c2` / `exp_c3` columns:
```python
    with exp_c2:
        exp_start, exp_end = date_range_nav(
            session_key_start="export_start",
            session_key_end="export_end",
            label_start="From date",
            label_end="To date",
        )
```

- [ ] **Step 3: Add import for `date_range_nav` if not present**

Run: Read top of `tabs/settings_tab.py` imports

If `date_range_nav` is not imported from `components`, add:
```python
from components.navigation import date_range_nav
```

- [ ] **Step 4: Verify the file runs**

Run: `python -c "import tabs.settings_tab"` — no output means success.

- [ ] **Step 5: Commit**

```bash
git add tabs/settings_tab.py
git commit -m "refactor: replace inline export date inputs with date_range_nav()"
```

---

## Spec Coverage Check

- [x] `date_nav()` refactored with consistent format — Task 1
- [x] `date_range_nav()` added as reusable component — Task 2
- [x] `report_tab.py` uses shared `date_nav()` — Task 3
- [x] `analytics_tab.py` uses shared `date_range_nav()` — Task 4
- [x] `settings_tab.py` uses shared `date_range_nav()` — Task 5
- [x] All date inputs use `DD/MM/YYYY` format — Tasks 1, 2
- [x] Analytics retains period selectbox UX — preserved in Task 4
- [x] Date range validation (start <= end) — Task 2
