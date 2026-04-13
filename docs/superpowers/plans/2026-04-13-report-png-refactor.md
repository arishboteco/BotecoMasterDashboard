# Report PNG Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the 4 identified bugs/oddities in the Report tab PNG generation, standardize formatting across all sections, and fix the category section row spacing.

**Architecture:** All changes are in `sheet_reports.py` (PNG rendering) and `report_tab.py` (data assembly). The core issue is inconsistent figure sizing causing category/service sections to have too much whitespace between rows, plus data flow bugs in the single-outlet MTD path.

**Tech Stack:** Python, matplotlib, Streamlit

---

## Root Cause Analysis

### Bug 1: Category PNG row spacing too wide
The `_fig_for_section` function uses `h = min(cap_h, 0.5 + 0.52 * max(n_rows, min_rows))`. For the category section with 6 categories, `n_rows = n_cat + 4 = 10`, but `min_rows=6` and `cap_h=21.0`. The `0.52` inches-per-row multiplier is calibrated for the sales summary (which has 24+ rows), making small sections like category (8 visual rows) get bloated figures. The `min_rows` floor also inflates small sections.

The actual row height in axis coordinates is `row_h = 0.038`. For a figure with `n_data_rows` actual rows at `DPI=150`, the correct height is approximately `(banner + header + n_data_rows * row_h_axis_space) / total_axis_range`, but since `ax.set_ylim(cur_y - 0.04, 1.0)` adjusts dynamically, the figure just needs to be tall enough to not clip.

### Bug 2: Single-outlet MTD data mismatch
In `report_tab.py:368-369`, when viewing a single outlet from a multi-outlet context, per-outlet MTD category/service data (`_single_outlet_cat`, `_single_outlet_svc`) are only built when `len(ctx.report_loc_ids) > 1`. But even for context with 1 location, if `multi_outlet` is True (meaning there are 2+ outlets in scope), the outlet-specific cat/svc should be built.

### Bug 3: 9-month lookback hack
The `_start_mo` calculation in `report_tab.py:194-207` and `322-332` uses a loop-style hack instead of proper `dateutil.relativedelta` or manual month arithmetic. Works but is fragile.

### Bug 4: `_single_outlet_footfall` always None
In `report_tab.py:303`, `per_outlet_footfall` for single-outlet view is always set to `None`, so the legacy footfall path is always used unless `per_outlet_footfall_metrics` is populated. This is actually correct behavior (metrics path is preferred), but the fallback variable is misleading dead code.

---

## Task 1: Fix figure sizing to eliminate row spacing inconsistency

**Files:**
- Modify: `sheet_reports.py:1620-1627` (`_fig_for_section`)

The root problem: `_fig_for_section` uses a fixed `0.52` inches-per-estimated-row formula that doesn't account for the actual content height. The correct approach is to size figures based on actual content drawn, not estimated rows.

**Strategy:** Instead of estimating rows before drawing, we'll adjust `_fig_for_section` to accept a tighter height-per-row ratio and lower the `min_rows` floor for category/service sections. The `0.52` factor creates ~78px per row at 150 DPI, but `row_h=0.038` in a 1.0-axis-range figure only needs ~40-45px per row when the total content is compact.

- [ ] **Step 1: Change the height-per-row formula**

In `sheet_reports.py`, update `_fig_for_section`:

```python
def _fig_for_section(
    n_rows: int, min_rows: int = 4, cap_h: float = 20.0, w: float = 8.5
) -> Tuple[plt.Figure, plt.Axes]:
    h = min(cap_h, 0.5 + 0.42 * max(n_rows, min_rows))
    fig, ax = plt.subplots(figsize=(w, h), dpi=DPI)
    fig.patch.set_facecolor(C_PAGE)
    ax.set_facecolor(C_PAGE)
    return fig, ax
```

Change `0.52` to `0.42`. This reduces per-row allocation from ~78px to ~63px at 150 DPI, which matches the actual visual density of `row_h=0.038` in sections with fewer than 15 rows.

- [ ] **Step 2: Tighten category section figure sizing**

In `sheet_reports.py` around line 1714-1715, change:

```python
    # Category
    n_cat = len(mc) or 3
    fig, ax = _fig_for_section(n_cat + 4, min_rows=6, cap_h=21.0, w=fig_w)
```

To:

```python
    # Category
    n_cat = len(mc) or 3
    fig, ax = _fig_for_section(n_cat + 4, min_rows=4, cap_h=16.0, w=fig_w)
```

Lower `min_rows` from 6→4 and `cap_h` from 21→16. The actual content is typically 8-10 rows (header + 6 categories + totals), and `0.42 * 10 = 4.2 + 0.5 = 4.7"` which is much more compact than the previous `0.52 * 10 = 5.7"`.

- [ ] **Step 3: Tighten service section figure sizing**

In `sheet_reports.py` around line 1728-1729, change:

```python
    n_svc = len(ms) or 3
    fig, ax = _fig_for_section(n_svc + 4, min_rows=5, cap_h=18.0, w=fig_w)
```

To:

```python
    n_svc = len(ms) or 3
    fig, ax = _fig_for_section(n_svc + 4, min_rows=4, cap_h=14.0, w=fig_w)
```

Same reasoning — service typically has 5-7 rows.

- [ ] **Step 4: Tighten sales summary min_rows**

In `sheet_reports.py` around line 1702-1703, change:

```python
    est_rows = 10 + n_pay + n_tax + 12  # MTD + forecast rows
    fig, ax = _fig_for_section(est_rows, min_rows=12, cap_h=36.0, w=fig_w)
```

To:

```python
    est_rows = 10 + n_pay + n_tax + 12  # MTD + forecast rows
    fig, ax = _fig_for_section(est_rows, min_rows=10, cap_h=36.0, w=fig_w)
```

This doesn't materially affect the sales summary (it usually has 20+ rows), but makes the minimum less inflated when there's very little data.

- [ ] **Step 5: Run tests to verify no breakage**

Run: `pytest tests/ -v`
Expected: All existing tests pass.

- [ ] **Step 6: Visually verify by running the app**

Run: `streamlit run app.py`
Expected: Category and Service sections have tighter row spacing, matching the Sales Summary density. No text clipping or overlap.

- [ ] **Step 7: Commit**

```bash
git add sheet_reports.py
git commit -m "fix: tighten PNG figure sizing for category/service sections"
```

---

## Task 2: Fix single-outlet MTD data mismatch

**Files:**
- Modify: `tabs/report_tab.py:286-370`

The bug: When `multi_outlet` is True and user selects a single outlet, `_single_outlet_cat` and `_single_outlet_svc` are only built when `len(ctx.report_loc_ids) > 1`. But even with 1 location in context, the per-outlet category/service MTD should use that location's data.

Actually, re-reading the code: `ctx.report_loc_ids` is always the list of location IDs for the current user. When `multi_outlet` is True, there are 2+ locations. So `len(ctx.report_loc_ids) > 1` is equivalent to `multi_outlet`. The real issue is more subtle — let me trace through:

When `multi_outlet` is True AND `len(ctx.report_loc_ids) > 1`:
- Lines 306-318: `_single_outlet_cat` and `_single_outlet_svc` are built with per-outlet data ✓
- Lines 358-363: `_single_outlet_mtd_cat` and `_single_outlet_mtd_svc` are built ✓

When `multi_outlet` is True BUT `len(ctx.report_loc_ids) == 1` (impossible since multi_outlet means 2+):
- This case can't happen, so the guard is correct.

When `multi_outlet` is False (single outlet):
- Lines 221-229: `mtd_cat`, `mtd_svc` are correctly built from the single location_id ✓
- `per_outlet_cat` and `per_outlet_svc` stay None ✓

So **Bug 2 doesn't actually exist** — the code is correct. The apparent mismatch I initially described was a misread. However, the **real issue** is that `_build_mtd_maps` on line 316 is called directly (not cached), while `_build_mtd_maps_cached` on line 310 is used for the category. This is a minor performance issue.

- [ ] **Step 1: Fix uncached MTD call for single-outlet svc**

In `tabs/report_tab.py`, change line ~316 from:

```python
                    _single_outlet_svc = [
                        (name, _build_mtd_maps([lid], y_m[0], y_m[1], date_str)[1])
                        for lid, name, _ in outlets_bundle
                        if lid == _selected_lid
                    ]
```

To:

```python
                    _single_outlet_svc = [
                        (name, _build_mtd_maps_cached([lid], y_m[0], y_m[1], date_str)[1])
                        for lid, name, _ in outlets_bundle
                        if lid == _selected_lid
                    ]
```

- [ ] **Step 2: Run tests**

Run: `pytest tests/ -v`
Expected: All tests pass.

- [ ] **Step 3: Commit**

```bash
git add tabs/report_tab.py
git commit -m "fix: use cached MTD maps for single-outlet service data"
```

---

## Task 3: Replace 9-month lookback hack with proper date arithmetic

**Files:**
- Modify: `tabs/report_tab.py:320-337`

The month subtraction loop is 15 lines of fragile date math. Replace with standard `date` arithmetic.

- [ ] **Step 1: Add helper in `utils.py`**

Add to `utils.py`:

```python
def subtract_months(dt: "date", months: int) -> "date":
    """Subtract N months from a date, landing on the first day of the resulting month."""
    year = dt.year - (months // 12)
    month = dt.month - (months % 12)
    if month <= 0:
        year -= 1
        month += 12
    return dt.replace(year=year, month=month, day=1)
```

- [ ] **Step 2: Replace multi-outlet lookback (lines 194-207) in report_tab.py**

Change:
```python
            _today = datetime.now().date()
            _end = _today.strftime("%Y-%m-%d")
            _start_mo = _today
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
```

To:
```python
            _today = datetime.now().date()
            _end = _today.strftime("%Y-%m-%d")
            _start_mo_dt = utils.subtract_months(_today, 9)
            _start_mo_str = _start_mo_dt.strftime("%Y-%m-%d")
            _days_since_monday = _today.weekday()
            _current_week_monday = _today - timedelta(days=_days_since_monday)
            _start_wk = (_current_week_monday - timedelta(weeks=3)).strftime("%Y-%m-%d")
```

- [ ] **Step 3: Replace single-outlet lookback (lines 322-337) in report_tab.py**

Change:
```python
                    _today = datetime.now().date()
                    _end = _today.strftime("%Y-%m-%d")
                    _start_mo = _today
                    for _ in range(9):
                        _m = _start_mo.month - 1
                        if _m == 0:
                            _m = 12
                            _start_mo = _start_mo.replace(
                                year=_start_mo.year - 1, month=_m
                            )
                        else:
                            _start_mo = _start_mo.replace(month=_m)
                    _start_mo_str = _start_mo.replace(day=1).strftime("%Y-%m-%d")
                    _days_since_monday = _today.weekday()
                    _current_week_monday = _today - timedelta(days=_days_since_monday)
                    _start_wk = (_current_week_monday - timedelta(weeks=3)).strftime(
                        "%Y-%m-%d"
                    )
```

To:
```python
                    _today = datetime.now().date()
                    _end = _today.strftime("%Y-%m-%d")
                    _start_mo_dt = utils.subtract_months(_today, 9)
                    _start_mo_str = _start_mo_dt.strftime("%Y-%m-%d")
                    _days_since_monday = _today.weekday()
                    _current_week_monday = _today - timedelta(days=_days_since_monday)
                    _start_wk = (_current_week_monday - timedelta(weeks=3)).strftime(
                        "%Y-%m-%d"
                    )
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/ -v`
Expected: All tests pass.

- [ ] **Step 5: Commit**

```bash
git add utils.py tabs/report_tab.py
git commit -m "refactor: replace month-subtraction loops with subtract_months helper"
```

---

## Task 4: Format standardization — consistent row height and padding across all sections

**Files:**
- Modify: `sheet_reports.py`

The `row_h = 0.038` is hardcoded in each section. Standardize and also make the banner heights consistent. Currently:
- `_section_sales_summary`: banner_h=0.08, vertical start at 0.93
- `_section_category`: banner_h=0.065, vertical start at 0.995
- `_section_service`: banner_h=0.065, vertical start at 0.995
- `_section_footfall`: banner_h=0.065, vertical start at 0.995
- `_section_footfall_metrics`: banner_h=0.065, vertical start at 0.995

The sales summary uses different coordinate system (starts at 0.93 instead of 0.995). This makes sections render at different vertical scales, causing inconsistent spacing.

- [ ] **Step 1: Standardize sales summary banner coordinates to match other sections**

In `_section_sales_summary` (around lines 648-650), change:

```python
    banner_h = 0.08
    banner_y = 0.93
```

To:

```python
    banner_h = 0.065
    banner_top = 0.995
    banner_y = banner_top - banner_h
```

Then update all references within `_section_sales_summary` that use `banner_y`:
- Replace `banner_y + banner_h` with `banner_top`
- Replace `0.012, banner_y + banner_h - 0.018` with `0.012, banner_top - 0.018`
- Replace `0.012, banner_y + banner_h - 0.048` with `0.012, banner_top - 0.045`
- Replace `0.988, banner_y + banner_h - 0.018` with `0.988, banner_top - 0.018`
- Replace `0.988, banner_y + banner_h - 0.048` with `0.988, banner_top - 0.045`

This makes the sales summary banner match the category/service sections (0.065 height, 0.995 top).

- [ ] **Step 2: Update sales summary banner content positions**

The full `_section_sales_summary` banner block changes from:

```python
    banner_h = 0.08
    banner_y = 0.93
    _card(ax, 0, banner_y, 1.0, banner_h, color=C_BANNER, border=C_BANNER)
    _hbar(ax, 0, banner_y + banner_h, 1.0, h=0.005, color=C_BRAND)
    _label(
        ax,
        0.012,
        banner_y + banner_h - 0.018,
        f"{location_name.upper()}  —  END OF DAY REPORT",
        size=11.5,
        color=C_WHITE,
        weight="bold",
    )
    _label(
        ax,
        0.012,
        banner_y + banner_h - 0.048,
        day_lbl,
        size=9.5,
        color=C_DATE_LABEL,
    )
    _label(
        ax,
        0.988,
        banner_y + banner_h - 0.018,
        f"{pct_tgt:.0f}% of target",
        size=11.0,
        color=ach_color,
        weight="bold",
        ha="right",
    )
    _label(
        ax,
        0.988,
        banner_y + banner_h - 0.048,
        _r(r.get("net_total", 0)) + " net",
        size=9.5,
        color=C_WHITE,
        ha="right",
    )

    # ── Column headers ───────────────────────────────────────────────────
    row_h = 0.038
    cur_y = banner_y - 0.01
```

To:

```python
    banner_h = 0.065
    banner_top = 0.995
    banner_y = banner_top - banner_h
    _card(ax, 0, banner_y, 1.0, banner_h, color=C_BANNER, border=C_BANNER)
    _hbar(ax, 0, banner_top, 1.0, h=0.005, color=C_BRAND)
    _label(
        ax,
        0.012,
        banner_top - 0.018,
        f"{location_name.upper()}  —  END OF DAY REPORT",
        size=11.5,
        color=C_WHITE,
        weight="bold",
    )
    _label(
        ax,
        0.012,
        banner_top - 0.045,
        day_lbl,
        size=9.5,
        color=C_DATE_LABEL,
    )
    _label(
        ax,
        0.988,
        banner_top - 0.018,
        f"{pct_tgt:.0f}% of target",
        size=11.0,
        color=ach_color,
        weight="bold",
        ha="right",
    )
    _label(
        ax,
        0.988,
        banner_top - 0.045,
        _r(r.get("net_total", 0)) + " net",
        size=9.5,
        color=C_WHITE,
        ha="right",
    )

    # ── Column headers ───────────────────────────────────────────────────
    row_h = 0.038
    cur_y = banner_y - 0.01
```

- [ ] **Step 3: Run tests**

Run: `pytest tests/ -v`
Expected: All tests pass.

- [ ] **Step 4: Visual verification**

Run: `streamlit run app.py`
Expected: All 4 PNG sections now start at the same vertical position (0.995) with same banner height (0.065). Row spacing is consistent. No overlap or clipping.

- [ ] **Step 5: Commit**

```bash
git add sheet_reports.py
git commit -m "fix: standardize banner layout and row spacing across all PNG sections"
```

---

## Task 5: Fix the `_single_outlet_footfall` dead code and simplify footfall path logic

**Files:**
- Modify: `tabs/report_tab.py:300-304`

The variable `_single_outlet_footfall` is set to `None` and never reassigned in the multi-outlet branch. The `per_outlet_footfall` parameter passed to `generate_sheet_style_report_sections` is always either `None` (single outlet) or the main `per_outlet_footfall` (multi-outlet, all-outlet view). The individual outlet never gets per-outlet footfall data through the legacy path — it always uses `per_outlet_footfall_metrics`.

This is fine functionally, but the dead variable is confusing. Remove it.

- [ ] **Step 1: Remove unused `_single_outlet_footfall` variable**

In `tabs/report_tab.py`, remove the declaration on line 303:

```python
                _single_outlet_footfall = None
```

And update the `generate_sheet_style_report_sections` call on line 375:

Change:
```python
                    per_outlet_footfall=_single_outlet_footfall,
```

To:
```python
                    per_outlet_footfall=None,
```

- [ ] **Step 2: Remove unused `per_outlet_footfall` variable in the else branch**

In `tabs/report_tab.py` around line 218-229, change:

```python
            per_outlet_footfall = None
            per_outlet_cat = None
            per_outlet_svc = None
```

To keep just what's needed (cat/svc are used, footfall isn't):
```python
            per_outlet_cat = None
            per_outlet_svc = None
```

And around line 226-228, change:
```python
            per_outlet_footfall = None
            per_outlet_footfall_metrics = None
            per_outlet_cat = None
            per_outlet_svc = None
```

To:
```python
            per_outlet_footfall_metrics = None
            per_outlet_cat = None
            per_outlet_svc = None
```

Also remove `per_outlet_footfall` from the main multi-outlet branch (lines 218) and the `generate_sheet_style_report_sections` call (line 240).

Actually — `per_outlet_footfall` IS used in the main section generation call at line 240. Let me re-check...

Looking again at the main multi-outlet flow (lines 190-243), `per_outlet_footfall` is set to `None` at line 218. This means the footfall sections will always use the `footfall_metrics` path (preferred) or the legacy `month_footfall_rows` path. The `per_outlet_footfall` param on the `generate_sheet_style_report_sections` call at line 240 passes `per_outlet_footfall` which is `None`. This is correct — it should remain `None` because metrics are preferred.

So the only dead variable is `_single_outlet_footfall` in the single-outlet branch.

- [ ] **Step 1 (revised): Remove `_single_outlet_footfall` from single-outlet branch**

In `tabs/report_tab.py`, remove line 303:
```python
                _single_outlet_footfall = None
```

And change line 375 from:
```python
                    per_outlet_footfall=_single_outlet_footfall,
```

To:
```python
                    per_outlet_footfall=None,
```

- [ ] **Step 2: Run tests**

Run: `pytest tests/ -v`
Expected: All tests pass.

- [ ] **Step 3: Commit**

```bash
git add tabs/report_tab.py
git commit -m "refactor: remove unused _single_outlet_footfall variable"
```

---

## Summary of Changes

| Task | File | What Changes |
|------|------|-------------|
| 1 | `sheet_reports.py` | Tighten `_fig_for_section` row multiplier (0.52→0.42), lower min_rows/cap_h for category/service |
| 2 | `tabs/report_tab.py` | Use `_build_mtd_maps_cached` instead of `_build_mtd_maps` on line 316 |
| 3 | `utils.py`, `tabs/report_tab.py` | Add `subtract_months` helper, replace 2 loop hacks |
| 4 | `sheet_reports.py` | Standardize sales summary banner to match other sections (0.065h, 0.995 top) |
| 5 | `tabs/report_tab.py` | Remove dead `_single_outlet_footfall` variable |