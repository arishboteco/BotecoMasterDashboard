# UPI GPay Razorpay Split Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split generic Growth Report UPI totals into GPay and Razorpay using explicit Growth columns when available, otherwise using Item Report `Payment Type` as the fallback split source.

**Architecture:** Extend the Item Report parser to emit `payment_split_by_date` metadata without changing category output. Add a small merge helper in `smart_upload.py` that applies Item-derived splits only when Growth has generic UPI and no explicit GPay/Razorpay split. Existing `payment_method_sales`, report bundle, PNG, and WhatsApp rendering paths then consume the normalized split.

**Tech Stack:** Python, pandas Excel parsing, Streamlit upload flow, pytest, Ruff.

---

### Task 1: Extract GPay/Razorpay Split From Item Report

**Files:**
- Modify: `uploads/parsers/item_report_category_summary.py`
- Test: `tests/test_growth_item_import.py`

- [ ] **Step 1: Write the failing parser test**

Add this test to `TestItemReportCategoryParser` in `tests/test_growth_item_import.py`:

```python
    def test_meta_has_payment_split_by_date_from_payment_type(self):
        from uploads.parsers.item_report_category_summary import parse_item_report_category_summary

        content = _item_report_bytes()
        rows, errors, meta = parse_item_report_category_summary(content, "test.xlsx", location_id=1)

        assert not errors
        assert rows
        assert meta["payment_split_by_date"] == {
            "2026-04-01": [
                {"payment_method": "GPay", "payment_key": "gpay", "amount": 805.0}
            ]
        }
```

Update `_item_report_bytes()` test helper so the two successful rows use GPay and total `805.0`:

```python
"Payment Type": ["GPay", "G PAY"],
```

- [ ] **Step 2: Run parser test to verify it fails**

Run: `python -m pytest tests/test_growth_item_import.py::TestItemReportCategoryParser::test_meta_has_payment_split_by_date_from_payment_type -q`

Expected: FAIL with missing `payment_split_by_date`.

- [ ] **Step 3: Add payment type normalization helpers**

In `uploads/parsers/item_report_category_summary.py`, add near internal helpers:

```python
def _payment_method_from_item_type(value: Any) -> Optional[Dict[str, str]]:
    """Normalize Item Report payment type to split methods used by reports."""
    key = _norm(value)
    if not key:
        return None
    compact = key.replace(" ", "")
    if compact in {"gpay", "googlepay"} or ("google" in key and "pay" in key):
        return {"payment_method": "GPay", "payment_key": "gpay"}
    if "razorpay" in compact:
        return {"payment_method": "Razorpay", "payment_key": "razorpay"}
    return None
```

- [ ] **Step 4: Accumulate payment split metadata**

In `parse_item_report_category_summary()`, resolve the payment type column:

```python
    payment_type_col = colmap.get("payment type")
```

Add a bucket before the row loop:

```python
    payment_split_buckets: Dict[str, Dict[str, Dict[str, Any]]] = {}
```

Inside the success-row path, after `final_total_val` is known and after non-success statuses are skipped, add:

```python
        if payment_type_col is not None and payment_type_col < len(row):
            method = _payment_method_from_item_type(row.iloc[payment_type_col])
            if method:
                split_for_date = payment_split_buckets.setdefault(date_str, {})
                split_row = split_for_date.setdefault(
                    method["payment_key"],
                    {
                        "payment_method": method["payment_method"],
                        "payment_key": method["payment_key"],
                        "amount": 0.0,
                    },
                )
                split_row["amount"] += final_total_val
```

Before building `meta`, build sorted output:

```python
    payment_split_by_date = {
        date: [
            {
                "payment_method": row["payment_method"],
                "payment_key": row["payment_key"],
                "amount": round(float(row["amount"] or 0), 2),
            }
            for row in sorted(split_rows.values(), key=lambda item: item["payment_key"])
            if float(row["amount"] or 0) > 0
        ]
        for date, split_rows in sorted(payment_split_buckets.items())
    }
```

Add it to `meta`:

```python
        "payment_split_by_date": payment_split_by_date,
```

- [ ] **Step 5: Run parser test to verify it passes**

Run: `python -m pytest tests/test_growth_item_import.py::TestItemReportCategoryParser::test_meta_has_payment_split_by_date_from_payment_type -q`

Expected: PASS.

### Task 2: Apply Item-Derived Split to Growth UPI Fallback

**Files:**
- Modify: `smart_upload.py`
- Test: `tests/test_growth_item_import.py`

- [ ] **Step 1: Write the fallback merge tests**

Add these tests to `TestDatabaseWritesNewFlow` in `tests/test_growth_item_import.py`:

```python
    def test_item_payment_split_replaces_generic_growth_upi(self):
        from smart_upload import _apply_item_payment_split_to_daily_row

        row = {
            "date": "2026-04-01",
            "upi_sales": 805.0,
            "gpay_sales": 0.0,
            "payment_methods": [],
        }
        split = [
            {"payment_method": "GPay", "payment_key": "gpay", "amount": 305.0},
            {"payment_method": "Razorpay", "payment_key": "razorpay", "amount": 500.0},
        ]

        _apply_item_payment_split_to_daily_row(row, split)

        assert row["upi_sales"] == 0.0
        assert row["gpay_sales"] == 305.0
        assert row["payment_methods"] == [
            {"payment_method": "Razorpay", "payment_key": "razorpay", "amount": 500.0}
        ]

    def test_item_payment_split_keeps_unmatched_upi_remainder(self):
        from smart_upload import _apply_item_payment_split_to_daily_row

        row = {"date": "2026-04-01", "upi_sales": 1000.0, "gpay_sales": 0.0}
        split = [
            {"payment_method": "GPay", "payment_key": "gpay", "amount": 300.0},
            {"payment_method": "Razorpay", "payment_key": "razorpay", "amount": 500.0},
        ]

        _apply_item_payment_split_to_daily_row(row, split)

        assert row["upi_sales"] == 200.0
        assert row["gpay_sales"] == 300.0
        assert row["payment_methods"] == [
            {"payment_method": "Razorpay", "payment_key": "razorpay", "amount": 500.0}
        ]
```

- [ ] **Step 2: Run merge tests to verify they fail**

Run: `python -m pytest tests/test_growth_item_import.py::TestDatabaseWritesNewFlow::test_item_payment_split_replaces_generic_growth_upi tests/test_growth_item_import.py::TestDatabaseWritesNewFlow::test_item_payment_split_keeps_unmatched_upi_remainder -q`

Expected: FAIL because `_apply_item_payment_split_to_daily_row` does not exist.

- [ ] **Step 3: Add the merge helper**

Add this helper in `smart_upload.py` near new-flow processing helpers:

```python
def _apply_item_payment_split_to_daily_row(
    row: Dict[str, Any],
    item_split: List[Dict[str, Any]],
) -> None:
    """Replace generic UPI with Item Report GPay/Razorpay split when possible."""
    upi_total = round(float(row.get("upi_sales", 0) or 0), 2)
    if upi_total <= 0 or not item_split:
        return
    existing_methods = {m.get("payment_key") for m in row.get("payment_methods") or []}
    if float(row.get("gpay_sales", 0) or 0) > 0 or "razorpay" in existing_methods:
        return

    split_total = round(sum(float(m.get("amount", 0) or 0) for m in item_split), 2)
    if split_total <= 0:
        return
    scale = min(1.0, upi_total / split_total) if split_total > upi_total else 1.0
    applied_total = 0.0
    payment_methods = list(row.get("payment_methods") or [])
    payment_methods = [m for m in payment_methods if m.get("payment_key") not in {"gpay", "razorpay"}]

    for method in item_split:
        amount = round(float(method.get("amount", 0) or 0) * scale, 2)
        if amount <= 0:
            continue
        applied_total += amount
        if method.get("payment_key") == "gpay":
            row["gpay_sales"] = round(float(row.get("gpay_sales", 0) or 0) + amount, 2)
        elif method.get("payment_key") == "razorpay":
            payment_methods.append(
                {
                    "payment_method": "Razorpay",
                    "payment_key": "razorpay",
                    "amount": amount,
                }
            )

    row["payment_methods"] = payment_methods
    row["upi_sales"] = round(max(0.0, upi_total - applied_total), 2)
```

- [ ] **Step 4: Run merge tests to verify they pass**

Run: `python -m pytest tests/test_growth_item_import.py::TestDatabaseWritesNewFlow::test_item_payment_split_replaces_generic_growth_upi tests/test_growth_item_import.py::TestDatabaseWritesNewFlow::test_item_payment_split_keeps_unmatched_upi_remainder -q`

Expected: PASS.

### Task 3: Wire Item Split Metadata Into New Upload Flow

**Files:**
- Modify: `smart_upload.py`
- Test: `tests/test_growth_item_import.py`

- [ ] **Step 1: Write integration-style merge test**

Add this test to `TestDatabaseWritesNewFlow` in `tests/test_growth_item_import.py`:

```python
    def test_item_payment_split_applied_to_daily_rows_by_location_and_date(self):
        from smart_upload import _apply_item_payment_splits_to_daily_rows

        daily_by_loc = {
            1: [
                {"date": "2026-04-01", "upi_sales": 805.0, "gpay_sales": 0.0},
                {"date": "2026-04-02", "upi_sales": 100.0, "gpay_sales": 0.0},
            ]
        }
        split_by_loc = {
            1: {
                "2026-04-01": [
                    {"payment_method": "GPay", "payment_key": "gpay", "amount": 305.0},
                    {"payment_method": "Razorpay", "payment_key": "razorpay", "amount": 500.0},
                ]
            }
        }

        _apply_item_payment_splits_to_daily_rows(daily_by_loc, split_by_loc)

        assert daily_by_loc[1][0]["upi_sales"] == 0.0
        assert daily_by_loc[1][0]["gpay_sales"] == 305.0
        assert daily_by_loc[1][0]["payment_methods"] == [
            {"payment_method": "Razorpay", "payment_key": "razorpay", "amount": 500.0}
        ]
        assert daily_by_loc[1][1]["upi_sales"] == 100.0
```

- [ ] **Step 2: Run integration-style test to verify it fails**

Run: `python -m pytest tests/test_growth_item_import.py::TestDatabaseWritesNewFlow::test_item_payment_split_applied_to_daily_rows_by_location_and_date -q`

Expected: FAIL because `_apply_item_payment_splits_to_daily_rows` does not exist.

- [ ] **Step 3: Add multi-row merge helper**

Add this helper in `smart_upload.py` below `_apply_item_payment_split_to_daily_row`:

```python
def _apply_item_payment_splits_to_daily_rows(
    daily_by_loc: Dict[int, List[Dict[str, Any]]],
    payment_split_by_loc: Dict[int, Dict[str, List[Dict[str, Any]]]],
) -> None:
    """Apply Item Report payment splits to parsed Growth daily rows."""
    for loc_id, daily_rows in daily_by_loc.items():
        split_by_date = payment_split_by_loc.get(loc_id, {})
        if not split_by_date:
            continue
        for row in daily_rows:
            _apply_item_payment_split_to_daily_row(row, split_by_date.get(str(row.get("date")), []))
```

- [ ] **Step 4: Store Item Report split metadata and apply after item parsing**

In `_process_new_flow_files()`, add a local bucket near `item_service_by_loc`:

```python
    item_payment_split_by_loc: Dict[int, Dict[str, List[Dict[str, Any]]]] = defaultdict(dict)
```

After storing `service_sales_by_date`, store payment splits:

```python
        for date_str, payment_split in (meta.get("payment_split_by_date") or {}).items():
            item_payment_split_by_loc[loc_id][date_str] = payment_split
```

After the item-files loop and before complimentary merge, apply splits:

```python
    _apply_item_payment_splits_to_daily_rows(daily_by_loc, item_payment_split_by_loc)
```

- [ ] **Step 5: Run integration-style test to verify it passes**

Run: `python -m pytest tests/test_growth_item_import.py::TestDatabaseWritesNewFlow::test_item_payment_split_applied_to_daily_rows_by_location_and_date -q`

Expected: PASS.

### Task 4: Focused Verification

**Files:**
- Verify: `uploads/parsers/item_report_category_summary.py`
- Verify: `smart_upload.py`
- Verify: `tests/test_growth_item_import.py`

- [ ] **Step 1: Run focused parser/upload tests**

Run:

```bash
python -m pytest tests/test_growth_item_import.py -q
```

Expected: PASS.

- [ ] **Step 2: Run touched-file lint**

Run:

```bash
python -m ruff check uploads/parsers/item_report_category_summary.py smart_upload.py tests/test_growth_item_import.py --select E,F,I,B
```

Expected: `All checks passed!`

- [ ] **Step 3: Manual smoke-check parsed local files if available**

Run a local parser script against available Growth + Item Reports and verify a date with generic Growth UPI now produces `gpay_sales`/Razorpay split and no duplicate UPI amount.

---

## Self-Review

- Spec coverage: Tasks cover Item Report extraction, Growth UPI fallback replacement, mismatch remainder handling, and focused verification.
- Placeholder scan: No TBD/TODO placeholders remain; each implementation step contains concrete code.
- Type consistency: Metadata uses `payment_split_by_date`; merge helpers use `payment_method`, `payment_key`, and `amount`, matching existing `payment_methods` rows.
