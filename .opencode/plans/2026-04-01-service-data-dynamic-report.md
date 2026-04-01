# Service Data from Dynamic Report Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract Lunch/Dinner meal-period service data from the Dynamic Report CSV's "Created Date Time" column so service data displays in reports and analytics.

**Architecture:** Modify `dynamic_report_parser.py` to accumulate meal-period revenue per row using the `"Created Date Time"` column, building a `"services"` list in each per-day output record — matching the format already produced by `pos_parser.py` and `timing_parser.py`. No database or UI changes needed; the existing pipeline already handles the `"services"` key.

**Tech Stack:** Python, pandas, pytest

---

## Context

### Current Data Flow

The pipeline already supports service data end-to-end:
- `pos_parser.py` produces `services` from timestamps (lines 342-346)
- `timing_parser.py` produces `services` from meal-period labels (line 269)
- `smart_upload.py` merges services at line 492-494 and attaches timing services at line 574-585
- `database.py` saves/loads services to `service_sales` table (lines 497-506, 835-839)
- `sheet_reports.py` renders services in PNG reports (lines 621-713)
- `analytics_tab.py` displays meal-period charts (lines 396-449)

**The gap:** `dynamic_report_parser.py` (the PRIMARY data source) produces NO `"services"` key.

### Meal Period Rules
- **Before 18:00** → Lunch
- **18:00 and after** → Dinner
- No Breakfast period

### Dynamic Report CSV Columns
The CSV has a `"Created Date Time"` column containing datetime values. The parser currently only uses `"Bill Date"` for grouping.

---

## File Structure

| File | Change |
|------|--------|
| `dynamic_report_parser.py` | Add meal-period extraction from "Created Date Time" column; include `"services"` key in output records |
| `tests/test_dynamic_report_parser.py` | New test file for the `_meal_from_time` helper and service data in parser output |

---

### Task 1: Add `_meal_from_time` helper function and service accumulation

**Files:**
- Modify: `dynamic_report_parser.py`
- Test: `tests/test_dynamic_report_parser.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_dynamic_report_parser.py`:

```python
"""Tests for dynamic_report_parser helper functions and service data extraction."""

import pytest
from dynamic_report_parser import _meal_from_time


class TestMealFromTime:
    def test_before_6pm_is_lunch(self):
        assert _meal_from_time("2024-03-15 14:30:00") == "Lunch"

    def test_at_6pm_is_dinner(self):
        assert _meal_from_time("2024-03-15 18:00:00") == "Dinner"

    def test_after_6pm_is_dinner(self):
        assert _meal_from_time("2024-03-15 21:15:00") == "Dinner"

    def test_morning_is_lunch(self):
        assert _meal_from_time("2024-03-15 09:00:00") == "Lunch"

    def test_none_returns_none(self):
        assert _meal_from_time(None) is None

    def test_empty_string_returns_none(self):
        assert _meal_from_time("") is None

    def test_nan_returns_none(self):
        assert _meal_from_time("nan") is None

    def test_invalid_string_returns_none(self):
        assert _meal_from_time("not-a-time") is None
```

Also add an integration-style test for the full parser producing services:

```python
class TestDynamicReportServiceData:
    def test_parser_produces_services_key(self):
        from io import BytesIO
        from dynamic_report_parser import parse_dynamic_report

        csv_content = (
            "Bill Date,Bill No,Pax,Net Amount,Gross Sale,Created Date Time\n"
            "2024-03-15,B001,2,500.0,550.0,2024-03-15 12:30:00\n"
            "2024-03-15,B002,4,800.0,880.0,2024-03-15 19:00:00\n"
        )
        records, notes = parse_dynamic_report(csv_content.encode("utf-8"), "test.csv")
        assert records is not None
        assert len(records) == 1
        assert "services" in records[0]
        svc_types = [s["type"] for s in records[0]["services"]]
        assert "Lunch" in svc_types
        assert "Dinner" in svc_types

    def test_service_amounts_match_net_total(self):
        from dynamic_report_parser import parse_dynamic_report

        csv_content = (
            "Bill Date,Bill No,Pax,Net Amount,Gross Sale,Created Date Time\n"
            "2024-03-15,B001,2,500.0,550.0,2024-03-15 12:30:00\n"
            "2024-03-15,B002,4,300.0,330.0,2024-03-15 12:45:00\n"
        )
        records, _ = parse_dynamic_report(csv_content.encode("utf-8"), "test.csv")
        lunch = next(s for s in records[0]["services"] if s["type"] == "Lunch")
        assert lunch["amount"] == 800.0

    def test_no_created_datetime_column_no_services(self):
        from dynamic_report_parser import parse_dynamic_report

        csv_content = (
            "Bill Date,Bill No,Pax,Net Amount,Gross Sale\n"
            "2024-03-15,B001,2,500.0,550.0\n"
        )
        records, _ = parse_dynamic_report(csv_content.encode("utf-8"), "test.csv")
        assert records is not None
        # services key should still exist but be empty
        assert records[0].get("services") == []
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_dynamic_report_parser.py -v
```

Expected: All tests fail — `_meal_from_time` doesn't exist, and parser doesn't produce `"services"`.

- [ ] **Step 3: Implement `_meal_from_time` helper**

Add this function to `dynamic_report_parser.py` after the `_safe_int` function (around line 66):

```python
import pandas as pd
from typing import Any, Optional


def _meal_from_time(ts_val: Any) -> Optional[str]:
    """Classify a datetime value as 'Lunch' (before 18:00) or 'Dinner' (18:00+).

    Args:
        ts_val: Raw value from the 'Created Date Time' column.

    Returns:
        'Lunch', 'Dinner', or None if unparseable.
    """
    if ts_val is None:
        return None
    s = str(ts_val).strip()
    if s in ("", "nan", "None"):
        return None
    try:
        ts = pd.Timestamp(s)
    except Exception:
        return None
    if pd.isna(ts):
        return None
    if ts.hour < 18:
        return "Lunch"
    return "Dinner"
```

- [ ] **Step 4: Add service accumulation to the day dict init**

In the `days[date_raw]` dict initialization (line 147-164), add a `"meals"` accumulator:

Change the day dict init from:
```python
        if date_raw not in days:
            days[date_raw] = {
                "date": date_raw,
                "covers": 0,
                "net_total": 0.0,
                "gross_total": 0.0,
                "discount": 0.0,
                "service_charge": 0.0,
                "cgst": 0.0,
                "sgst": 0.0,
                "cash_sales": 0.0,
                "card_sales": 0.0,
                "gpay_sales": 0.0,
                "zomato_sales": 0.0,
                "other_sales": 0.0,
                "order_count": 0,
                "bills": set(),
                "categories": {},
            }
```

To:
```python
        if date_raw not in days:
            days[date_raw] = {
                "date": date_raw,
                "covers": 0,
                "net_total": 0.0,
                "gross_total": 0.0,
                "discount": 0.0,
                "service_charge": 0.0,
                "cgst": 0.0,
                "sgst": 0.0,
                "cash_sales": 0.0,
                "card_sales": 0.0,
                "gpay_sales": 0.0,
                "zomato_sales": 0.0,
                "other_sales": 0.0,
                "order_count": 0,
                "bills": set(),
                "categories": {},
                "meals": {},
            }
```

- [ ] **Step 5: Accumulate meal-period revenue per row**

After the category breakdown loop (after line 194), add meal-period accumulation. Get the column reference for "Created Date Time" alongside the other column refs (around line 136):

Add after line 136:
```python
    cdt_col = col_map.get("created date time")
```

Then after line 194 (after the category breakdown loop), add:
```python
        # Meal period (service) breakdown
        if cdt_col:
            meal = _meal_from_time(row.get(cdt_col))
            if meal:
                net_val = _safe_float(row.get(net_col, 0))
                day["meals"][meal] = day["meals"].get(meal, 0.0) + net_val
```

- [ ] **Step 6: Build `"services"` list in output records**

In the output record building section (around line 208), add the services list. Change the record from:

```python
        record = {
            "date": date_str,
            "covers": day["covers"],
            "net_total": round(day["net_total"], 2),
            "gross_total": round(day["gross_total"], 2),
            "discount": round(day["discount"], 2),
            "service_charge": round(day["service_charge"], 2),
            "cgst": round(day["cgst"], 2),
            "sgst": round(day["sgst"], 2),
            "cash_sales": round(day["cash_sales"], 2),
            "card_sales": round(day["card_sales"], 2),
            "gpay_sales": round(day["gpay_sales"], 2),
            "zomato_sales": round(day["zomato_sales"], 2),
            "other_sales": round(day["other_sales"], 2),
            "order_count": bill_count,
            "categories": categories,
            "file_type": "dynamic_report",
        }
```

To:
```python
        services = [
            {"type": k, "amount": round(v, 2)}
            for k, v in sorted(day["meals"].items(), key=lambda x: -x[1])
            if v > 0
        ]

        record = {
            "date": date_str,
            "covers": day["covers"],
            "net_total": round(day["net_total"], 2),
            "gross_total": round(day["gross_total"], 2),
            "discount": round(day["discount"], 2),
            "service_charge": round(day["service_charge"], 2),
            "cgst": round(day["cgst"], 2),
            "sgst": round(day["sgst"], 2),
            "cash_sales": round(day["cash_sales"], 2),
            "card_sales": round(day["card_sales"], 2),
            "gpay_sales": round(day["gpay_sales"], 2),
            "zomato_sales": round(day["zomato_sales"], 2),
            "other_sales": round(day["other_sales"], 2),
            "order_count": bill_count,
            "categories": categories,
            "services": services,
            "file_type": "dynamic_report",
        }
```

- [ ] **Step 7: Run tests to verify they pass**

```bash
pytest tests/test_dynamic_report_parser.py -v
```

Expected: All 11 tests pass.

- [ ] **Step 8: Run full test suite to ensure no regressions**

```bash
pytest
```

Expected: All tests pass (existing `test_pos_parser.py` tests + new `test_dynamic_report_parser.py` tests).

---

## Self-Review

### Spec Coverage
- ✅ Extract meal period from "Created Date Time" column
- ✅ Before 18:00 = Lunch, 18:00+ = Dinner
- ✅ No Breakfast period
- ✅ Service data shows in reports (existing pipeline handles it)
- ✅ Service data shows in analytics (existing pipeline handles it)

### Placeholder Scan
- ✅ No TBD/TODO placeholders
- ✅ All code shown explicitly
- ✅ No "similar to" references

### Type Consistency
- ✅ `_meal_from_time` returns `Optional[str]` matching the pattern from `pos_parser._meal_from_timestamp`
- ✅ `services` list format matches `pos_parser.py:342-346` and `timing_parser.py:269`
- ✅ `"meals"` accumulator uses same pattern as `"categories"` dict

---

Plan complete. Two execution options:

**1. Subagent-Driven (recommended)** - Dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
