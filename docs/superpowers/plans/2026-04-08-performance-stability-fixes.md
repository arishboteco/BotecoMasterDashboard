# Performance & Stability Fixes Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** Fix the critical and high-priority performance/stability issues identified in the Boteco dashboard codebase.

**Architecture:** Changes are targeted at the data-access and query layer. The primary goals are: (1) eliminate N+1 query patterns, (2) add proper cache invalidation, (3) harden the database layer against edge cases, and (4) add security-hardening fixes.

**Tech Stack:** Python 3.11+, SQLite, Streamlit, pytest.

---

## Task 1: Fix N+1 Query in `scope.py` — `get_daily_summary_for_scope`

**Files:**
- Modify: `scope.py:111-119`

- [ ] **Step 1: Read existing scope.py to confirm current implementation**

- [ ] **Step 2: Add batch query function `get_daily_summaries_for_locations` to `database_reads.py`**

```python
@st.cache_data(ttl=120)
def get_daily_summaries_for_locations(
    location_ids: List[int], start_date: str, end_date: str
) -> List[Dict]:
    """All summaries for multiple locations in a date range, single query."""
    if not location_ids:
        return []
    placeholders = ",".join("?" * len(location_ids))
    with db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            f"""
            SELECT * FROM daily_summaries
            WHERE location_id IN ({placeholders}) AND date >= ? AND date <= ?
            ORDER BY location_id, date
            """,
            (*location_ids, start_date, end_date),
        )
        rows = cursor.fetchall()
    return [dict(row) for row in rows]
```

- [ ] **Step 3: Update `scope.py` `get_daily_summary_for_scope` to use batch query**

```python
def get_daily_summary_for_scope(
    location_ids: List[int], date_str: str
) -> Optional[Dict[str, Any]]:
    if not location_ids:
        return None
    rows = database_reads.get_daily_summaries_for_locations(location_ids, date_str, date_str)
    parts = [r for r in rows if r.get("date") == date_str]
    return aggregate_daily_summaries(parts)
```

- [ ] **Step 4: Update `scope.py` `get_daily_report_bundle` to use batch query**

The function at `scope.py:174-189` loops per location. Replace with single `get_daily_summaries_for_locations` call:

```python
def get_daily_report_bundle(
    location_ids: List[int], date_str: str
) -> Tuple[List[Tuple[int, str, Dict[str, Any]]], Optional[Dict[str, Any]]]:
    if not location_ids:
        return [], None

    rows = database_reads.get_daily_summaries_for_locations(location_ids, date_str, date_str)
    rows_by_loc: Dict[int, List[Dict]] = defaultdict(list)
    for r in rows:
        rows_by_loc[r["location_id"]].append(r)

    outlets: List[Tuple[int, str, Dict[str, Any]]] = []
    parts_raw: List[Dict[str, Any]] = []

    for lid in location_ids:
        st = database.get_location_settings(lid)
        name = str(st["name"]) if st and st.get("name") else str(lid)
        monthly_tgt = (
            float(st["target_monthly_sales"])
            if st and st.get("target_monthly_sales")
            else float(config.MONTHLY_TARGET)
        )
        loc_rows = rows_by_loc.get(lid, [])
        if loc_rows:
            base = dict(loc_rows[0])
            parts_raw.append(loc_rows[0])
        else:
            base = _synthetic_daily_summary(lid, date_str)
        enriched = enrich_summary_for_display(base, [lid], monthly_tgt, date_str)
        outlets.append((lid, name, enriched))

    if not parts_raw:
        return [], None

    combined = aggregate_daily_summaries(parts_raw)
    if combined is None:
        return [], None
    monthly_all = sum_location_monthly_targets(location_ids)
    combined_e = enrich_summary_for_display(
        combined, location_ids, monthly_all, date_str
    )
    return outlets, combined_e
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/ -v --tb=short 2>&1 | head -60
```

---

## Task 2: Add SQLite Timeout & Fix `check_same_thread`

**Files:**
- Modify: `database.py:63-67`

- [ ] **Step 1: Change `get_connection` to use timeout and remove `check_same_thread=False`**

```python
def get_connection():
    """Get database connection with row factory."""
    conn = sqlite3.connect(DATABASE_PATH, timeout=10.0)
    conn.row_factory = sqlite3.Row
    return conn
```

`check_same_thread=False` is removed since Streamlit is single-threaded and this was masking potential issues.

- [ ] **Step 2: Run tests**

```bash
pytest tests/ -v --tb=short 2>&1 | head -60
```

---

## Task 3: Add `secrets.compare_digest` for Session Token Comparison

**Files:**
- Modify: `database_auth.py:183-207`

- [ ] **Step 1: Add `secrets` import and replace `==` with `secrets.compare_digest`**

At top of `database_auth.py`, ensure:
```python
import secrets
```

In `validate_session_token` (line ~203), change:
```python
WHERE s.token IN (?, ?)
```
This currently does a regular string comparison. The fix is in `delete_session_token` — change:
```python
token_hash = database._hash_session_token(token)
with database.db_connection() as conn:
    conn.execute(
        "DELETE FROM user_sessions WHERE token IN (?, ?)",
        (token_hash, token),
    )
```
The `IN` clause with two values means we compare twice. Use `secrets.compare_digest` in a subquery or change to proper comparison. The safest fix:

```python
def validate_session_token(token: str) -> Optional[Dict]:
    """Return user dict for a valid non-expired token, or None."""
    if not token:
        return None
    token_hash = database._hash_session_token(token)
    with database.db_connection() as conn:
        row = conn.execute(
            """
            SELECT
                u.id,
                u.username,
                u.email,
                u.role,
                u.location_id,
                u.created_at,
                l.name AS location_name
            FROM user_sessions s
            JOIN users u ON u.id = s.user_id
            LEFT JOIN locations l ON l.id = u.location_id
            WHERE s.token = ?
              AND s.expires_at > datetime('now')
            """,
            (token_hash,),
        ).fetchone()
    if row:
        if secrets.compare_digest(token_hash, database._hash_session_token(token)):
            return dict(row)
    return None
```

Actually, since we hash before storing, we already compare hashes. The real issue is `delete_session_token` uses `IN (?, ?)` which leaks timing. Fix it to a single parameter:

```python
def delete_session_token(token: str) -> None:
    """Remove a session token on logout."""
    if not token:
        return
    token_hash = database._hash_session_token(token)
    with database.db_connection() as conn:
        conn.execute(
            "DELETE FROM user_sessions WHERE token = ?",
            (token_hash,),
        )
        conn.commit()
```

- [ ] **Step 2: Run tests**

```bash
pytest tests/ -v --tb=short 2>&1 | head -60
```

---

## Task 4: Add Cache Invalidation on Upload

**Files:**
- Modify: `tabs/upload_tab.py`
- Modify: `database_reads.py`
- Modify: `database_analytics.py`

- [ ] **Step 1: Add cache key registry in `database_reads.py`**

Add a helper to clear cached data for a specific location:

```python
def clear_location_cache(location_id: int) -> None:
    """Clear all @st.cache_data caches for a specific location.
    
    Called after successful upload to ensure subsequent reads
    reflect the new data immediately.
    """
    get_summaries_for_month.clear(location_id=location_id)
    get_category_mtd_totals.clear(location_id=location_id)
    get_service_mtd_totals.clear(location_id=location_id)
    get_recent_summaries.clear(location_id=location_id)
```

And import the function at the module level where needed.

- [ ] **Step 2: Call `clear_location_cache` in `upload_tab.py` after successful save**

In `tabs/upload_tab.py` around line 196 (after save loop), add:
```python
from database_reads import clear_location_cache

# After saving, clear caches for affected locations
for lid in upload_result.location_results:
    clear_location_cache(lid)
```

- [ ] **Step 3: Verify the import works**

```bash
cd C:\Github\BotecoMasterDashboard && python -c "import tabs.upload_tab; print('OK')"
```

---

## Task 5: Optimize File Matching with Dict in `smart_upload.py`

**Files:**
- Modify: `smart_upload.py:390-580`

- [ ] **Step 1: Build `filename_to_fr` dict once after classification**

In `process_smart_upload`, after building `file_results` (around line 416), add:
```python
filename_to_fr: Dict[str, FileResult] = {fr.filename: fr for fr in file_results}
```

Then replace all `next((f for f in file_results if f.filename == fname), None)` with:
```python
filename_to_fr.get(fname)
```

There are 5 occurrences at approximately lines 425, 448, 476, 521, 550.

- [ ] **Step 2: Verify no other occurrences**

```bash
rg "next.*file_results.*filename" --type py
```

Should return no results after the fix.

---

## Task 6: Batch Queries in `backfill_weekday_weighted_targets`

**Files:**
- Modify: `database_writes.py:359-430`

- [ ] **Step 1: Rewrite to use a single query for all location rows**

Replace the per-location loop with a batch approach:

```python
def backfill_weekday_weighted_targets() -> Tuple[int, int]:
    import utils

    with database.db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT k FROM app_meta WHERE k = ?", ("weekday_target_backfill",)
        )
        if cursor.fetchone():
            database.logger.info("weekday_target_backfill already run, skipping.")
            return 0, 0

    # Get all location IDs and their summaries in one query
    with database.db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT ds.id, ds.date, ds.location_id
            FROM daily_summaries ds
            ORDER BY ds.location_id, ds.date
            """
        )
        all_rows = cursor.fetchall()

    if not all_rows:
        return 0, 0

    rows_by_loc: Dict[int, List[Tuple[int, str]]] = defaultdict(list)
    for row in all_rows:
        rows_by_loc[row["location_id"]].append((row["id"], row["date"]))

    location_ids = list(rows_by_loc.keys())

    # Pre-fetch all recent summaries in one query
    with database.db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT location_id, date, net_total
            FROM daily_summaries
            WHERE location_id IN ({})
            ORDER BY location_id, date DESC
            """.format(",".join("?" * len(location_ids))),
            list(location_ids),
        )
        recent_rows = cursor.fetchall()

    recent_by_loc: Dict[int, List[Dict]] = defaultdict(list)
    for row in recent_rows:
        recent_by_loc[row["location_id"]].append(dict(row))

    # Build weekday_mix per location once
    weekday_mix_by_loc: Dict[int, dict] = {}
    location_settings: Dict[int, Dict] = {}
    day_targets_by_loc: Dict[int, dict] = {}
    monthly_by_loc: Dict[int, float] = {}

    for loc_id in location_ids:
        recent = recent_by_loc.get(loc_id, [])
        weekday_mix_by_loc[loc_id] = utils.compute_weekday_mix(recent)
        st = database.get_location_settings(loc_id)
        location_settings[loc_id] = st
        monthly = (
            float(st["target_monthly_sales"])
            if st and st.get("target_monthly_sales")
            else float(config.MONTHLY_TARGET)
        )
        monthly_by_loc[loc_id] = monthly
        day_targets_by_loc[loc_id] = utils.compute_day_targets(monthly, weekday_mix_by_loc[loc_id])

    # Batch update all rows
    with database.db_connection() as conn:
        cursor = conn.cursor()
        updated_total = 0
        for loc_id, loc_rows in rows_by_loc.items():
            day_targets = day_targets_by_loc[loc_id]
            for row_id, row_date in loc_rows:
                new_target = utils.get_target_for_date(day_targets, row_date)
                cursor.execute(
                    "UPDATE daily_summaries SET target = ? WHERE id = ?",
                    (new_target, row_id),
                )
                updated_total += 1
        conn.commit()

        cursor.execute(
            "INSERT OR REPLACE INTO app_meta (k, v) VALUES (?, ?)",
            ("weekday_target_backfill", "done"),
        )
        conn.commit()

    database.logger.info(
        f"backfill_weekday_weighted_targets complete: {updated_total} rows across {len(location_ids)} locations"
    )
    return updated_total, len(location_ids)
```

- [ ] **Step 2: Run tests**

```bash
pytest tests/ -v --tb=short 2>&1 | head -60
```

---

## Task 7: Fix `calculate_mtd_metrics_multi` to Use `get_summaries_for_month_multi`

**Files:**
- Modify: `pos_parser.py:627-665`

- [ ] **Step 1: Replace per-location loop with `get_summaries_for_month_multi`**

```python
@st.cache_data(ttl=300)
def calculate_mtd_metrics_multi(
    location_ids: List[int],
    target_monthly: float,
    year: Optional[int] = None,
    month: Optional[int] = None,
    as_of_date: Optional[str] = None,
) -> Dict:
    """MTD across multiple locations using single batch query."""
    from database import get_summaries_for_month_multi

    if year is None or month is None:
        t = datetime.now()
        year, month = t.year, t.month

    summaries = get_summaries_for_month_multi(location_ids, year, month)
    if as_of_date:
        cap = str(as_of_date)[:10]
        summaries = [s for s in summaries if str(s.get("date", ""))[:10] <= cap]

    total_covers = sum(s.get("covers", 0) or 0 for s in summaries)
    total_sales = sum(s.get("net_total", 0) or 0 for s in summaries)
    total_discount = sum(s.get("discount", 0) or 0 for s in summaries)
    days_counted = len([s for s in summaries if (s.get("net_total", 0) or 0) > 0])

    avg_daily = total_sales / days_counted if days_counted > 0 else 0
    pct_target = (total_sales / target_monthly) * 100 if target_monthly > 0 else 0

    return {
        "mtd_total_covers": total_covers,
        "mtd_net_sales": total_sales,
        "mtd_discount": total_discount,
        "mtd_avg_daily": avg_daily,
        "mtd_target": target_monthly,
        "mtd_pct_target": pct_target,
        "days_counted": days_counted,
    }
```

- [ ] **Step 2: Run tests**

```bash
pytest tests/ -v --tb=short 2>&1 | head -60
```

---

## Task 8: Add Division-by-Zero Guards in `scope.py`

**Files:**
- Modify: `scope.py:101-108`

- [ ] **Step 1: Make guards explicit in `aggregate_daily_summaries`**

```python
tgt = float(out.get("target") or 0)
net = float(out.get("net_total") or 0)
cov = int(out.get("covers") or 0)
out["pct_target"] = round((net / tgt) * 100, 2) if tgt and tgt > 0 else 0.0
out["apc"] = round(net / cov, 2) if cov and cov > 0 and net > 0 else 0.0
seats = sum_location_seat_counts(location_ids)
out["turns"] = round(cov / seats, 2) if seats and seats > 0 else round(cov / 100, 1) if cov else 0.0
```

- [ ] **Step 2: Run tests**

```bash
pytest tests/ -v --tb=short 2>&1 | head -60
```

---

## Task 9: Add `__init__.py` Export for `clear_location_cache`

**Files:**
- Modify: `database_reads.py`
- Modify: `database/__init__.py` (create if needed)

- [ ] **Step 1: Ensure `clear_location_cache` is exported**

In `database_reads.py`, the function is already defined. Verify it's importable:
```bash
python -c "from database_reads import clear_location_cache; print('OK')"
```

If `database/__init__.py` exists as a package init, check the export path. The module is `database_reads` so the import in `upload_tab.py` should be:
```python
from database_reads import clear_location_cache
```
(no `database.` prefix since `upload_tab.py` already imports `database`)

- [ ] **Step 2: Verify upload tab imports cleanly**

```bash
python -c "import tabs.upload_tab; print('OK')"
```

---

## Verification

- [ ] **Step 1: Run full test suite**

```bash
pytest tests/ -v --tb=short 2>&1
```

- [ ] **Step 2: Run lint check (if configured)**

```bash
ruff check . 2>&1 | head -40
```

- [ ] **Step 3: Verify app imports correctly**

```bash
python -c "import app; print('App imports OK')" 2>&1
```
