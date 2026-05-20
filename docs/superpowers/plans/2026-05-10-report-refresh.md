# Report Refresh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an in-app `Refresh report` button near the Report tab date controls that clears Report-tab caches and reruns the page.

**Architecture:** Keep the change local to the Report tab and report service. `report_service.clear_report_cache()` becomes the single cache-clearing entrypoint for Report bundle, MTD, and footfall caches; `tabs/report_tab.py` exposes a small button near the date picker that calls it, clears Streamlit cached data, marks a success message, and reruns.

**Tech Stack:** Python, Streamlit, pytest source-level tests, existing `cache_manager` report caches.

---

### Task 1: Expand Report Service Cache Clearing

**Files:**
- Modify: `services/report_service.py`
- Test: `tests/test_report_service.py`

- [ ] **Step 1: Write the failing test**

Append this test to `tests/test_report_service.py`:

```python
def test_clear_report_cache_clears_all_report_cache_stores():
    report_service._REPORT_CACHE[("report",)] = "stale-report"
    report_service._MTD_CACHE[("mtd",)] = "stale-mtd"
    report_service._FOOT_CACHE[("foot",)] = "stale-foot"

    report_service.clear_report_cache()

    assert report_service._REPORT_CACHE == {}
    assert report_service._MTD_CACHE == {}
    assert report_service._FOOT_CACHE == {}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_report_service.py::test_clear_report_cache_clears_all_report_cache_stores -q`

Expected: FAIL because `_MTD_CACHE` and `_FOOT_CACHE` still contain stale entries.

- [ ] **Step 3: Write minimal implementation**

Update `services/report_service.py`:

```python
def clear_report_cache() -> None:
    """Clear cached daily report, MTD, and footfall data."""
    cache_manager.invalidate("report")
    cache_manager.invalidate("mtd")
    cache_manager.invalidate("foot")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_report_service.py::test_clear_report_cache_clears_all_report_cache_stores -q`

Expected: PASS.

### Task 2: Add Report Tab Refresh Control

**Files:**
- Modify: `tabs/report_tab.py`
- Test: `tests/test_report_tab.py`

- [ ] **Step 1: Write the failing source test**

Append this test to `tests/test_report_tab.py`:

```python
def test_report_tab_has_refresh_report_control():
    source = Path("tabs/report_tab.py").read_text(encoding="utf-8")

    assert "Refresh report" in source
    assert "report_refresh" in source
    assert "report_service.clear_report_cache()" in source
    assert "st.cache_data.clear()" in source
    assert "st.rerun()" in source
```

If `Path` is not imported in `tests/test_report_tab.py`, add:

```python
from pathlib import Path
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_report_tab.py::test_report_tab_has_refresh_report_control -q`

Expected: FAIL because the refresh control does not exist.

- [ ] **Step 3: Add a refresh helper**

Add this helper near `clear_report_cache()` in `tabs/report_tab.py`:

```python
def _refresh_report_data() -> None:
    """Clear Report tab caches and rerun the current page."""
    report_service.clear_report_cache()
    st.cache_data.clear()
    st.session_state["report_refresh_message"] = "Report data refreshed."
    st.rerun()
```

- [ ] **Step 4: Render the button near date controls**

In `tabs/report_tab.py`, render a `Refresh report` button near the existing date picker controls.

For the multi-outlet branch, change the columns from:

```python
_prev_col, _date_col, _next_col, _outlet_col = st.columns(
    [0.3, 1.2, 0.3, 4], vertical_alignment="center"
)
```

to:

```python
_prev_col, _date_col, _next_col, _outlet_col, _refresh_col = st.columns(
    [0.3, 1.2, 0.3, 3.2, 0.9], vertical_alignment="center"
)
```

Then add after the outlet control:

```python
with _refresh_col:
    st.button(
        "Refresh report",
        key="report_refresh",
        on_click=_refresh_report_data,
        help="Reload report data from the database.",
    )
```

For the single-outlet branch, replace:

```python
selected_date = date_nav(session_key="report_date", label="Report date")
```

with:

```python
_date_nav_col, _refresh_col = st.columns([4, 1], vertical_alignment="center")
with _date_nav_col:
    selected_date = date_nav(session_key="report_date", label="Report date")
with _refresh_col:
    st.button(
        "Refresh report",
        key="report_refresh",
        on_click=_refresh_report_data,
        help="Reload report data from the database.",
    )
```

- [ ] **Step 5: Show refresh confirmation**

After `date_str = selected_date.strftime("%Y-%m-%d")`, add:

```python
refresh_message = st.session_state.pop("report_refresh_message", None)
if refresh_message:
    st.success(refresh_message)
```

- [ ] **Step 6: Run test to verify it passes**

Run: `python -m pytest tests/test_report_tab.py::test_report_tab_has_refresh_report_control -q`

Expected: PASS.

### Task 3: Focused Verification

**Files:**
- Verify: `services/report_service.py`
- Verify: `tabs/report_tab.py`
- Verify: `tests/test_report_service.py`
- Verify: `tests/test_report_tab.py`

- [ ] **Step 1: Run focused tests**

Run:

```bash
python -m pytest tests/test_report_service.py tests/test_report_tab.py -q
```

Expected: PASS, except unrelated pre-existing failures should be documented with exact names and output.

- [ ] **Step 2: Run touched-file lint**

Run:

```bash
python -m ruff check services/report_service.py tabs/report_tab.py tests/test_report_service.py tests/test_report_tab.py --select E,F,I,B
```

Expected: `All checks passed!`

- [ ] **Step 3: Manual smoke check**

Run the app with `streamlit run app.py`, open the Report tab, select a historical date, click `Refresh report`, and confirm the report rerenders without restarting Streamlit.

---

## Self-Review

- Spec coverage: The plan adds the approved near-date-picker button, clears report-specific caches, clears Streamlit data cache, reruns the page, and shows confirmation.
- Placeholder scan: No placeholder steps or undefined implementation details remain.
- Type consistency: Function names and keys are consistent: `_refresh_report_data`, `report_refresh`, `report_refresh_message`, and `clear_report_cache`.
