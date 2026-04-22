# Whole Repo Quality Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Execute a single broad refactor batch that improves reliability and code organization without changing dashboard behavior.

**Architecture:** Keep runtime behavior stable while improving test determinism, parser resilience, and analytics aggregation structure. Use test-first slices for behavior changes and low-risk internal extraction for duplication cleanup. Validate all changes with full `pytest` before completion.

**Tech Stack:** Python 3.14, pytest, Streamlit, SQLite/Supabase compatibility layer

---

### Task 1: Stabilize Existing Quality Baseline

**Files:**
- Modify: `tests/test_database.py`

- [ ] **Step 1: Add deterministic DB fixture coverage for footfall tests**

```python
def test_returns_empty_for_no_data(self, initialized_db):
    result = database.get_monthly_footfall_multi([1], "2025-01-01", "2025-12-31")
    assert result == []
```

- [ ] **Step 2: Replace shape-only assertions with value assertions**

```python
assert result == [
    {"month": "2025-01", "covers": 30, "net_total": 2800.0, "gross_total": 3200.0, "total_days": 2},
    {"month": "2025-02", "covers": 5, "net_total": 600.0, "gross_total": 700.0, "total_days": 1},
]
```

- [ ] **Step 3: Verify tests**

Run: `python -m pytest tests/test_database.py -v`
Expected: PASS


### Task 2: Harden Smart Upload Status Parsing

**Files:**
- Modify: `tests/test_smart_upload.py`
- Modify: `smart_upload.py`

- [ ] **Step 1: Add failing regression test for `SuccessOrder` status variant**

```python
def test_accepts_successorder_status_rows(self):
    content = (
        "date,my_amount,status,payment_type\n"
        "2026-04-01,100,SuccessOrder,GPay\n"
    ).encode("utf-8")
    parsed, notes = smart_upload._parse_order_summary_csv(content, "orders.csv")
    assert parsed is not None
```

- [ ] **Step 2: Add failing regression test for spaced status variant**

```python
def test_accepts_success_order_status_with_space(self):
    content = (
        "date,my_amount,status,payment_type\n"
        "2026-04-01,120,Success Order,Card\n"
    ).encode("utf-8")
    parsed, notes = smart_upload._parse_order_summary_csv(content, "orders.csv")
    assert parsed is not None
```

- [ ] **Step 3: Implement minimal normalization-based fix**

```python
_SUCCESS_STATUSES = {"", "success", "successorder"}

def _normalize_status_token(value: Any) -> str:
    token = str(value or "").strip().lower()
    return token.replace(" ", "").replace("_", "").replace("-", "")
```

- [ ] **Step 4: Verify parser-specific suite**

Run: `python -m pytest tests/test_smart_upload.py -v`
Expected: PASS


### Task 3: Refactor Analytics Aggregation Internals (No Behavior Change)

**Files:**
- Modify: `database_analytics.py`
- Test: `tests/test_database.py`

- [ ] **Step 1: Extract shared fetch helper for daily summary rows**

```python
def _fetch_daily_summary_rows(
    location_ids: List[int], start_date: str, end_date: str, columns: List[str]
) -> List[Dict[str, Any]]:
    ...
```

- [ ] **Step 2: Extract month/week aggregation helpers**

```python
def _aggregate_monthly(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    ...

def _aggregate_weekly(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    ...
```

- [ ] **Step 3: Replace duplicated logic in public functions with helpers**

```python
rows = _fetch_daily_summary_rows(location_ids, start_date, end_date, [...])
return _aggregate_monthly(rows)
```

- [ ] **Step 4: Verify behavior with focused tests**

Run: `python -m pytest tests/test_database.py::TestGetMonthlyFootfallMulti -v`
Run: `python -m pytest tests/test_database.py::TestGetWeeklyFootfallMulti -v`
Expected: PASS


### Task 4: Full Validation Gate

**Files:**
- No code changes (verification only)

- [ ] **Step 1: Run full suite**

Run: `python -m pytest`
Expected: all tests pass

- [ ] **Step 2: Capture changed files and diff for review**

Run: `git status --short`
Run: `git diff -- smart_upload.py database_analytics.py tests/test_database.py tests/test_smart_upload.py`
Expected: only intended files changed
