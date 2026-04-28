# EOD Report Turns And Row Colors Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Correct EOD report turns to use configured seat count and add subtle semantic row backgrounds to the sales summary table.

**Architecture:** Keep calculation fixes in `scope.py`, where multi-location summaries are aggregated and enriched. Keep report styling local to `sheet_reports.py` by adding small row-style helpers used by the existing sales-summary table builders.

**Tech Stack:** Python 3.11, pytest, ReportLab table styling, existing Streamlit report generation code.

---

## File Structure

- Modify: `scope.py` to remove the stale `covers / 100` fallback from combined daily aggregation.
- Modify: `sheet_reports.py` to add semantic row background selection for EOD and MTD rows.
- Modify: `tests/test_validation_rules.py` to cover combined aggregation turns behavior.
- Modify: `tests/test_sheet_reports_formatting.py` to inspect generated `TableStyle` commands for semantic row backgrounds.

## Task 1: Fix Combined Turns Calculation

**Files:**
- Modify: `tests/test_validation_rules.py`
- Modify: `scope.py:132-139`

- [ ] **Step 1: Write the failing test**

Add this import near the existing imports in `tests/test_validation_rules.py`:

```python
import scope
```

Add this test after `test_turns_not_covers_over_100`:

```python
def test_aggregate_daily_summaries_does_not_fallback_to_covers_over_100():
    """Combined aggregation should not invent turns from covers / 100."""
    result = scope.aggregate_daily_summaries([
        {
            "date": "2026-04-27",
            "covers": 48,
            "net_total": 44010,
            "target": 400000,
        },
        {
            "date": "2026-04-27",
            "covers": 0,
            "net_total": 0,
            "target": 400000,
        },
    ])

    assert result is not None
    assert result["turns"] is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_validation_rules.py::test_aggregate_daily_summaries_does_not_fallback_to_covers_over_100 -v`

Expected: FAIL because `result["turns"]` is currently `0.5` from `round(cov / 100, 1)`.

- [ ] **Step 3: Write minimal implementation**

In `scope.py`, replace:

```python
out["turns"] = round(cov / 100, 1) if cov else 0.0
```

with:

```python
out["turns"] = None
```

This lets `enrich_summary_for_display()` calculate turns from summed `seat_count` via `parser.calculate_derived_metrics()`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_validation_rules.py::test_aggregate_daily_summaries_does_not_fallback_to_covers_over_100 -v`

Expected: PASS.

- [ ] **Step 5: Run existing turns tests**

Run: `pytest tests/test_validation_rules.py -v`

Expected: PASS.

## Task 2: Revise Semantic Row Backgrounds

**Files:**
- Modify: `tests/test_sheet_reports_formatting.py`
- Modify: `sheet_reports.py:880-1067`

- [ ] **Step 1: Write the failing style test**

Add this helper to `tests/test_sheet_reports_formatting.py` after `_has_dark_footer_band`:

```python
def _table_commands(elements):
    for element in elements:
        if isinstance(element, sheet_reports.Table):
            return list(element._cellStyles.commands if hasattr(element._cellStyles, "commands") else [])
    return []
```

If ReportLab does not expose commands through `_cellStyles.commands`, use this helper instead:

```python
def _table_commands(elements):
    for element in elements:
        if isinstance(element, sheet_reports.Table):
            style = getattr(element, "_argW", None)
            assert style is not None or element is not None
            return list(getattr(element, "_bkgrndcmds", []))
    return []
```

Update the sales summary row background test so it verifies section-based colors and no decorative zebra banding:

```python
def test_sales_summary_uses_section_based_row_backgrounds_without_zebra_banding():
    report_data = {
        "date": "2026-04-27",
        "covers": 48,
        "turns": 0.69,
        "gross_total": 49775,
        "net_total": 44010,
        "gpay_sales": 49775,
        "discount": 0,
        "complimentary": 0,
        "cgst": 1153,
        "sgst": 1153,
        "service_charge": 0,
        "mtd_total_covers": 2079,
        "apc": 917,
        "mtd_net_sales": 3311873,
        "mtd_discount": 1732,
        "mtd_complimentary": 0,
        "mtd_avg_daily": 122662,
        "mtd_target": 8000000,
        "mtd_pct_target": 46,
    }

    elements = sheet_reports._build_sales_summary(
        report_data,
        location_name="All locations",
        per_outlet=[("Bagmane", report_data), ("Indiqube", {"covers": 0})],
    )

    table = next(element for element in elements if isinstance(element, sheet_reports.Table))
    backgrounds = list(getattr(table, "_bkgrndcmds", []))

    assert _background_hex_for_label(table, "Covers") == sheet_reports.C_ROW_OPS
    assert _background_hex_for_label(table, "GPay") is None
    assert _background_hex_for_label(table, "SGST @ 2.5%") is None
    assert _background_hex_for_label(table, "Discount") == sheet_reports.C_ROW_DEDUCTION
    assert _background_hex_for_label(table, "Complimentary") == sheet_reports.C_ROW_EXCEPTION
    assert _background_hex_for_label(table, "Sales Target") == sheet_reports.C_ROW_TARGET_NEUTRAL
    assert _background_hex_for_label(table, "% of Target") == sheet_reports.C_ROW_TARGET_BAD
    assert _background_hex_for_label(table, "Forecast Month-End") == sheet_reports.C_ROW_FORECAST
    assert _background_hex_for_label(table, "Required Daily Run Rate") == sheet_reports.C_ROW_TARGET_WARN
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_sheet_reports_formatting.py::TestSalesSummaryRowBackgrounds::test_sales_summary_uses_section_backgrounds_without_zebra_banding -v`

Expected: FAIL because payment/tax rows still receive zebra banding and final rows do not have distinct backgrounds.

- [ ] **Step 3: Add color constants and helpers**

In `sheet_reports.py`, near existing color constants, add:

```python
C_ROW_OPS = "#E8F2FB"
C_ROW_DEDUCTION = "#FDECEC"
C_ROW_EXCEPTION = "#FFF4D8"
C_ROW_FORECAST = "#E8F2FB"
C_ROW_TARGET_NEUTRAL = "#EEF2F7"
C_ROW_TARGET_GOOD = "#EAF7EF"
C_ROW_TARGET_WARN = "#FFF4D8"
C_ROW_TARGET_BAD = "#FDECEC"
```

Near `_build_sales_summary`, add:

```python
OPS_ROWS = {"Covers", "Turns", "APC (Day)", "APC (Month)"}
DEDUCTION_ROWS = {"Discount", "MTD Discount"}
EXCEPTION_ROWS = {"Complimentary", "MTD Complimentary"}
TARGET_ROWS = {"% of Target", "Forecast vs Target"}


def _target_row_bg(color: str | None) -> str:
    if color == C_GREEN:
        return C_ROW_TARGET_GOOD
    if color == C_AMBER:
        return C_ROW_TARGET_WARN
    return C_ROW_TARGET_BAD


def _sales_summary_row_bg(label: str, status_color: str | None = None) -> str | None:
    if label in OPS_ROWS:
        return C_ROW_OPS
    if label in DEDUCTION_ROWS:
        return C_ROW_DEDUCTION
    if label in EXCEPTION_ROWS:
        return C_ROW_EXCEPTION
    if label == "Sales Target":
        return C_ROW_TARGET_NEUTRAL
    if label == "Forecast Month-End":
        return C_ROW_FORECAST
    if label in TARGET_ROWS:
        return _target_row_bg(status_color)
    if label == "Required Daily Run Rate":
        return C_ROW_TARGET_WARN if status_color != C_GREEN else C_ROW_TARGET_NEUTRAL
    return None
```

- [ ] **Step 4: Remove decorative zebra banding and apply semantic backgrounds only**

In `add_row()` inside `_build_sales_summary`, before the `if bg:` block, add:

```python
semantic_bg = bg or _sales_summary_row_bg(label, ach_color if key_or_fn == "pct_target" else None)
```

Replace:

```python
if bg:
    override_list.append(("BACKGROUND", (0, ri), (-1, ri), _hex(bg)))
elif row_idx % 2 == 1:
    override_list.append(("BACKGROUND", (0, ri), (-1, ri), _hex(C_BAND)))
```

with:

```python
if semantic_bg:
    override_list.append(("BACKGROUND", (0, ri), (-1, ri), _hex(semantic_bg)))
```

- [ ] **Step 5: Apply helper to MTD rows and final target rows**

Change the `add_mtd_row` signature from:

```python
def add_mtd_row(label, key_or_fn, fmt="currency", bold=False, right_color=None):
```

to:

```python
def add_mtd_row(label, key_or_fn, fmt="currency", bold=False, right_color=None):
```

Inside `add_mtd_row()`, replace:

```python
if mri % 2 == 1:
    ov.append(("BACKGROUND", (0, ri), (-1, ri), _hex(C_BAND)))
```

with:

```python
semantic_bg = _sales_summary_row_bg(label, right_color)
if semantic_bg:
    ov.append(("BACKGROUND", (0, ri), (-1, ri), _hex(semantic_bg)))
```

- [ ] **Step 6: Run semantic style test**

Run: `pytest tests/test_sheet_reports_formatting.py::TestSalesSummaryRowBackgrounds::test_sales_summary_uses_section_backgrounds_without_zebra_banding -v`

Expected: PASS.

## Task 3: Verify Report Output And Formatting

**Files:**
- Modify only if verification exposes a real regression.

- [ ] **Step 1: Run focused report tests**

Run: `pytest tests/test_sheet_reports_formatting.py tests/test_sheet_reports_sections.py -v`

Expected: PASS.

- [ ] **Step 2: Run scope and validation tests**

Run: `pytest tests/test_validation_rules.py tests/test_report_service.py -v`

Expected: PASS.

- [ ] **Step 3: Format touched files**

Run: `ruff format scope.py sheet_reports.py tests/test_validation_rules.py tests/test_sheet_reports_formatting.py`

Expected: command completes successfully.

- [ ] **Step 4: Lint touched files**

Run: `ruff check scope.py sheet_reports.py tests/test_validation_rules.py tests/test_sheet_reports_formatting.py --select E,F,I,B`

Expected: PASS.

- [ ] **Step 5: Inspect git diff**

Run: `git diff -- scope.py sheet_reports.py tests/test_validation_rules.py tests/test_sheet_reports_formatting.py docs/superpowers/specs/2026-04-28-eod-report-turns-row-colors-design.md docs/superpowers/plans/2026-04-28-eod-report-turns-row-colors.md`

Expected: diff contains only the turns fix, row background styling, tests, and docs.

## Self-Review

- Spec coverage: Task 1 covers turns calculation. Task 2 covers semantic row backgrounds. Task 3 covers verification.
- Placeholder scan: no TBD/TODO/fill-later items remain.
- Type consistency: helper names and color constants are consistent across the plan.
- Commit note: no commit steps are included because this workspace instruction says not to commit unless explicitly requested by the user.
