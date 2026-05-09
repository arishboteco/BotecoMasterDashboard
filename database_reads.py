"""Read/query operations for the new simplified database schema."""

from __future__ import annotations

import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import streamlit as st

import boteco_logger
from core.dates import month_bounds
from db.category_rows import CATEGORY_ROW_PREFIX
from db.table_names import (
    SQLITE_DAILY_SUMMARIES,
    SQLITE_ITEM_SALES,
    SQLITE_SERVICE_SALES,
    SUPABASE_CATEGORY_SUMMARY,
    SUPABASE_DAILY_SUMMARY,
)

logger = boteco_logger.get_logger(__name__)


def _execute_with_retry(query_builder, *, max_attempts: int = 3):
    """Execute a Supabase query, retrying on transient socket errors (EAGAIN / ReadError)."""
    import httpx

    delay = 0.5
    for attempt in range(max_attempts):
        try:
            return query_builder.execute()
        except httpx.ReadError:
            if attempt == max_attempts - 1:
                raise
            logger.warning(
                "Transient Supabase ReadError (attempt %d/%d), retrying in %.1fs",
                attempt + 1,
                max_attempts,
                delay,
            )
            time.sleep(delay)
            delay *= 2


_SUPABASE_COLUMN_RENAMES = {
    "complementary_amount": "complimentary",
}


def _normalize_row(row: Dict) -> Dict:
    for src, dst in _SUPABASE_COLUMN_RENAMES.items():
        if src in row:
            row[dst] = row.pop(src)
    return row


def _normalize_rows(rows: List[Dict]) -> List[Dict]:
    for r in rows:
        _normalize_row(r)
    return rows


def _sqlite_daily_table() -> str:
    """Legacy local schema table name (Supabase uses singular daily_summary)."""
    return SQLITE_DAILY_SUMMARIES


def _apply_override_single(
    summary: Optional[Dict], location_id: int, date: str
) -> Optional[Dict]:
    """Overlay manual footfall override on a single summary (or build synthetic)."""
    from services.footfall_override_service import apply_override_to_single

    return apply_override_to_single(summary, location_id, date)


def _apply_overrides_range(
    summaries: List[Dict],
    location_ids: List[int],
    start_date: str,
    end_date: str,
) -> List[Dict]:
    """Overlay manual footfall overrides over a range query and inject synthetics."""
    from services.footfall_override_service import apply_overrides

    return apply_overrides(summaries, location_ids, start_date, end_date)


def _reconcile_cover_split(lunch: int, dinner: int, covers: int) -> tuple[int, int]:
    """Scale a derived Lunch/Dinner split so it preserves stored total covers."""
    raw_total = lunch + dinner
    if raw_total <= 0 or covers <= 0 or raw_total == covers:
        return lunch, dinner
    scaled_lunch = round(covers * (lunch / raw_total))
    return scaled_lunch, covers - scaled_lunch


def _hydrate_supabase_footfall_splits(
    summaries: List[Dict], location_ids: List[int], start_date: str, end_date: str
) -> List[Dict]:
    """Derive missing Lunch/Dinner covers from Supabase bill_items pax timestamps."""
    if not summaries or not location_ids:
        return summaries

    import database
    from database_analytics import (
        _bill_items_success,
        _hour_from_created_datetime,
        _service_type_from_created_datetime,
    )
    from database_writes import LOCATION_ID_TO_RESTAURANT

    restaurant_to_location = {
        restaurant: int(location_id)
        for location_id, restaurant in LOCATION_ID_TO_RESTAURANT.items()
        if int(location_id) in {int(lid) for lid in location_ids}
    }
    if not restaurant_to_location:
        return summaries

    supabase = database.get_supabase_client()
    result = _execute_with_retry(
        supabase.table("bill_items")
        .select("restaurant,bill_date,bill_no,created_date_time,pax,net_amount,bill_status")
        .in_("restaurant", list(restaurant_to_location.keys()))
        .gte("bill_date", start_date)
        .lte("bill_date", end_date)
    )

    bills: Dict[tuple[int, str, str], Dict[str, Any]] = {}
    for row in result.data or []:
        if not _bill_items_success(row.get("bill_status")):
            continue
        location_id = restaurant_to_location.get(str(row.get("restaurant") or ""))
        bill_no = str(row.get("bill_no") or "").strip()
        if location_id is None or not bill_no:
            continue
        date = str(row.get("bill_date") or "")[:10]
        if not date:
            continue
        key = (location_id, date, bill_no)
        bucket = bills.setdefault(
            key,
            {"pax": 0, "net_amount": 0.0, "created_date_time": row.get("created_date_time")},
        )
        bucket["pax"] = max(int(bucket.get("pax") or 0), int(row.get("pax") or 0))
        bucket["net_amount"] += float(row.get("net_amount") or 0)
        if bucket.get("created_date_time") is None:
            bucket["created_date_time"] = row.get("created_date_time")

    grouped: Dict[tuple[int, str], List[Dict[str, Any]]] = {}
    for (location_id, date, _bill_no), bill in bills.items():
        if int(bill.get("pax") or 0) <= 0 and float(bill.get("net_amount") or 0) <= 0:
            continue
        grouped.setdefault((location_id, date), []).append(bill)

    split_by_key: Dict[tuple[int, str], Dict[str, int]] = {}
    for key, day_bills in grouped.items():
        hours = [
            hour
            for bill in day_bills
            if (hour := _hour_from_created_datetime(bill.get("created_date_time"))) is not None
        ]
        is_pos_12h_clock = bool(hours) and max(hours) <= 12
        split = {
            "lunch_covers": 0,
            "dinner_covers": 0,
            "lunch_sales": 0.0,
            "dinner_sales": 0.0,
        }
        for bill in day_bills:
            service_type = _service_type_from_created_datetime(
                bill.get("created_date_time"), is_pos_12h_clock
            )
            pax = int(bill.get("pax") or 0)
            net_amount = float(bill.get("net_amount") or 0)
            if service_type == "Lunch":
                split["lunch_covers"] += pax
                split["lunch_sales"] += net_amount
            else:
                split["dinner_covers"] += pax
                split["dinner_sales"] += net_amount
        split_by_key[key] = split

    hydrated: List[Dict] = []
    for summary in summaries:
        out = dict(summary)
        if out.get("lunch_covers") is not None or out.get("dinner_covers") is not None:
            hydrated.append(out)
            continue
        loc = out.get("location_id")
        date = str(out.get("date") or "")[:10]
        split = split_by_key.get((int(loc), date)) if loc is not None and date else None
        if split:
            covers = int(out.get("covers") or 0)
            lunch_raw = int(split["lunch_covers"])
            dinner_raw = int(split["dinner_covers"])
            if lunch_raw + dinner_raw > 0:
                lunch, dinner = _reconcile_cover_split(lunch_raw, dinner_raw, covers)
            else:
                sales_total = float(split["lunch_sales"] or 0) + float(split["dinner_sales"] or 0)
                if covers <= 0 or sales_total <= 0:
                    hydrated.append(out)
                    continue
                lunch = round(covers * (float(split["lunch_sales"] or 0) / sales_total))
                dinner = covers - lunch
            out["lunch_covers"] = lunch
            out["dinner_covers"] = dinner
        hydrated.append(out)
    return hydrated


def _inclusive_end_from_exclusive(date_str: str) -> str:
    """Convert YYYY-MM-DD exclusive boundary to inclusive previous date."""
    day = datetime.strptime(date_str, "%Y-%m-%d").date()
    return (day - timedelta(days=1)).strftime("%Y-%m-%d")


def _sqlite_categories_for_summary(conn, summary_id: int) -> List[Dict]:
    """Rebuild category aggregates saved with synthetic item_sales rows."""
    cur = conn.cursor()
    cur.execute(
        f"""
        SELECT category, qty, amount
        FROM {SQLITE_ITEM_SALES}
        WHERE summary_id = ?
          AND item_name LIKE ?
        """,
        (summary_id, f"{CATEGORY_ROW_PREFIX}%"),
    )
    out: List[Dict] = []
    for r in cur.fetchall():
        out.append(
            {
                "category": r["category"],
                "qty": int(r["qty"] or 0),
                "amount": float(r["amount"] or 0),
            }
        )
    return out


def _sqlite_services_for_summary(conn, summary_id: int) -> List[Dict]:
    """Load Lunch/Dinner (or other) service splits saved in service_sales."""
    cur = conn.cursor()
    cur.execute(
        f"""
        SELECT service_type, amount
        FROM {SQLITE_SERVICE_SALES}
        WHERE summary_id = ?
        ORDER BY service_type
        """,
        (summary_id,),
    )
    out: List[Dict] = []
    for r in cur.fetchall():
        amt = float(r["amount"] or 0)
        if amt <= 0:
            continue
        st = str(r["service_type"] or "").strip()
        out.append({"type": st, "amount": amt})
    return out


@st.cache_data(ttl=600)
def get_all_locations() -> List[Dict]:
    """Get all locations."""
    import database

    if database.use_supabase():
        supabase = database.get_supabase_client()
        result = _execute_with_retry(supabase.table("locations").select("*").order("name"))
        return result.data
    else:
        with database.db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM locations ORDER BY name")
            rows = cursor.fetchall()
        return [dict(row) for row in rows]


def peek_daily_net_sales(location_id: int, date: str) -> Optional[float]:
    """Return saved net_total for a day if a row exists."""
    import database

    if database.use_supabase():
        supabase = database.get_supabase_client()
        result = _execute_with_retry(
            supabase.table(SUPABASE_DAILY_SUMMARY)
            .select("net_total")
            .eq("location_id", location_id)
            .eq("date", date)
        )
        if not result.data:
            return None
        return float(result.data[0]["net_total"] or 0)
    else:
        tbl = _sqlite_daily_table()
        with database.db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"""
                SELECT net_total FROM {tbl}
                WHERE location_id = ? AND date = ?
                """,
                (location_id, date),
            )
            row = cursor.fetchone()
        if not row:
            return None
        return float(row["net_total"] or 0)


def peek_existing_net_sales_batch(location_id: int, dates: List[str]) -> Dict[str, float]:
    """Return {date: net_total} for dates that already have data.

    Single query instead of one per date — used by upload overlap detection.
    """
    import database

    if not dates:
        return {}

    if database.use_supabase():
        supabase = database.get_supabase_client()
        result = _execute_with_retry(
            supabase.table(SUPABASE_DAILY_SUMMARY)
            .select("date,net_total")
            .eq("location_id", location_id)
            .in_("date", dates)
        )
        return {row["date"]: float(row["net_total"] or 0) for row in result.data}
    else:
        tbl = _sqlite_daily_table()
        placeholders = ",".join("?" for _ in dates)
        with database.db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"SELECT date, net_total FROM {tbl} "
                f"WHERE location_id = ? AND date IN ({placeholders})",
                [location_id] + list(dates),
            )
            return {row["date"]: float(row["net_total"] or 0) for row in cursor.fetchall()}


def _detail_lists_for_daily_summary(location_id: int, date: str) -> tuple[List[Dict], List[Dict]]:
    """Build categories + services lists for PNG/report bundle (Supabase schema).

    daily_summary rows do not embed these; they live in category_summary and are
    derived for services from bill_items.
    """
    from database_analytics import (
        get_category_sales_grouped_for_date_range,
        get_service_sales_for_date_range,
    )

    cats_out: List[Dict] = []
    cat_rows = get_category_sales_grouped_for_date_range([location_id], date, date)
    for r in cat_rows or []:
        name = str(r.get("category") or "").strip()
        if not name:
            continue
        cats_out.append(
            {
                "category": name,
                "qty": int(r.get("qty") or 0),
                "amount": float(r.get("amount") or r.get("total") or 0),
            }
        )

    svcs_out: List[Dict] = []
    svc_rows = get_service_sales_for_date_range([location_id], date, date)
    for s in svc_rows or []:
        amt = float(s.get("amount") or 0)
        if amt <= 0:
            continue
        label = str(s.get("type") or s.get("service_type") or "").strip()
        if not label:
            continue
        svcs_out.append({"type": label, "amount": amt})

    return cats_out, svcs_out


def get_daily_summary(location_id: int, date: str) -> Optional[Dict]:
    """Get daily summary for a specific date."""
    import database

    if database.use_supabase():
        supabase = database.get_supabase_client()
        result = _execute_with_retry(
            supabase.table(SUPABASE_DAILY_SUMMARY)
            .select("*")
            .eq("location_id", location_id)
            .eq("date", date)
        )
        if result.data:
            d = _normalize_row(dict(result.data[0]))
            try:
                cats, svcs = _detail_lists_for_daily_summary(location_id, date)
                d["categories"] = cats
                d["services"] = svcs
            except (ValueError, TypeError, KeyError, RuntimeError) as ex:
                logger.warning(
                    "Detail list hydration failed in database_reads.py "
                    "location_id=%s date=%s error=%s",
                    location_id,
                    date,
                    ex,
                )
                d.setdefault("categories", [])
                d.setdefault("services", [])
        else:
            d = None
        return _apply_override_single(d, location_id, date)
    else:
        tbl = _sqlite_daily_table()
        with database.db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"SELECT * FROM {tbl} WHERE location_id = ? AND date = ?",
                (location_id, date),
            )
            row = cursor.fetchone()
            if not row:
                return _apply_override_single(None, location_id, date)
            d = dict(row)
            sid = int(d["id"])
            d["categories"] = _sqlite_categories_for_summary(conn, sid)
            d["services"] = _sqlite_services_for_summary(conn, sid)
            if not d["services"]:
                try:
                    from database_analytics import get_service_sales_for_date_range

                    svcs = get_service_sales_for_date_range([location_id], date, date)
                    d["services"] = [
                        {
                            "type": str(s.get("type") or s.get("service_type") or ""),
                            "amount": float(s.get("amount") or 0),
                        }
                        for s in (svcs or [])
                        if float(s.get("amount") or 0) > 0
                    ]
                except (ValueError, TypeError, KeyError, RuntimeError) as ex:
                    logger.warning(
                        (
                            "Service fallback query failed in database_reads.py "
                            "location_id=%s date=%s error=%s"
                        ),
                        location_id,
                        date,
                        ex,
                    )
        return _apply_override_single(d, location_id, date)


def get_summaries_for_date_range(
    location_id: int,
    start_date: str,
    end_date: str,
) -> List[Dict]:
    """Get daily summaries for a date range."""
    import database

    if database.use_supabase():
        supabase = database.get_supabase_client()
        result = _execute_with_retry(
            supabase.table(SUPABASE_DAILY_SUMMARY)
            .select("*")
            .eq("location_id", location_id)
            .gte("date", start_date)
            .lte("date", end_date)
            .order("date")
        )
        rows = _normalize_rows(list(result.data or []))
        rows = _hydrate_supabase_footfall_splits(rows, [location_id], start_date, end_date)
    else:
        tbl = _sqlite_daily_table()
        with database.db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"""
                SELECT * FROM {tbl}
                WHERE location_id = ? AND date >= ? AND date <= ?
                ORDER BY date
                """,
                (location_id, start_date, end_date),
            )
            rows = [dict(row) for row in cursor.fetchall()]
    return _apply_overrides_range(rows, [location_id], start_date, end_date)


@st.cache_data(ttl=600)
def get_summaries_for_month(location_id: int, year: int, month: int) -> List[Dict]:
    """Get daily summaries for a specific month."""
    start_date, exclusive_end_date = month_bounds(year, month)
    end_date = _inclusive_end_from_exclusive(exclusive_end_date)

    return get_summaries_for_date_range(location_id, start_date, end_date)


def get_summaries_for_date_range_multi(
    location_ids: List[int],
    start_date: str,
    end_date: str,
) -> List[Dict]:
    """Get daily summaries for multiple locations."""
    import database

    if database.use_supabase():
        supabase = database.get_supabase_client()
        result = _execute_with_retry(
            supabase.table(SUPABASE_DAILY_SUMMARY)
            .select("*")
            .in_("location_id", location_ids)
            .gte("date", start_date)
            .lte("date", end_date)
            .order("date")
        )
        rows = _normalize_rows(list(result.data or []))
        rows = _hydrate_supabase_footfall_splits(rows, list(location_ids), start_date, end_date)
    else:
        tbl = _sqlite_daily_table()
        with database.db_connection() as conn:
            cursor = conn.cursor()
            placeholders = ",".join("?" * len(location_ids))
            cursor.execute(
                f"""
                SELECT * FROM {tbl}
                WHERE location_id IN ({placeholders}) AND date >= ? AND date <= ?
                ORDER BY date
                """,
                (*location_ids, start_date, end_date),
            )
            rows = [dict(row) for row in cursor.fetchall()]
    return _apply_overrides_range(rows, list(location_ids), start_date, end_date)


def get_category_totals_for_date_range(
    location_ids: List[int],
    start_date: str,
    end_date: str,
) -> List[Dict]:
    """Get category totals for a date range."""
    import database

    if database.use_supabase():
        supabase = database.get_supabase_client()
        result = _execute_with_retry(
            supabase.table(SUPABASE_CATEGORY_SUMMARY)
            .select("*")
            .in_("location_id", location_ids)
            .gte("date", start_date)
            .lte("date", end_date)
        )
        return result.data
    else:
        tbl = _sqlite_daily_table()
        with database.db_connection() as conn:
            cursor = conn.cursor()
            placeholders = ",".join("?" * len(location_ids))
            cursor.execute(
                f"""
                SELECT
                    ds.location_id AS location_id,
                    ds.date AS date,
                    i.category AS category_name,
                    SUM(i.amount) AS net_amount,
                    SUM(i.qty) AS qty
                FROM {SQLITE_ITEM_SALES} i
                INNER JOIN {tbl} ds ON ds.id = i.summary_id
                WHERE ds.location_id IN ({placeholders})
                  AND ds.date >= ? AND ds.date <= ?
                  AND i.item_name LIKE ?
                GROUP BY ds.location_id, ds.date, i.category
                """,
                (
                    *location_ids,
                    start_date,
                    end_date,
                    f"{CATEGORY_ROW_PREFIX}%",
                ),
            )
            rows = cursor.fetchall()
        return [dict(row) for row in rows]


@st.cache_data(ttl=600)
def get_category_mtd_totals(
    location_ids: List[int],
    year: int,
    month: int,
) -> List[Dict]:
    """Get category totals for month-to-date."""
    start_date = f"{year}-{month:02d}-01"
    return get_category_totals_for_date_range(location_ids, start_date, "2999-12-31")


def get_mtd_totals_multi(location_ids: List[int], year: int, month: int) -> Dict[str, float]:
    """Get MTD totals across all locations for a month."""
    summaries = get_summaries_for_date_range_multi(
        location_ids,
        f"{year}-{month:02d}-01",
        "2999-12-31",
    )

    totals = {
        "net_total": 0.0,
        "gross_total": 0.0,
        "covers": 0,
        "discount": 0.0,
        "order_count": 0,
    }

    for s in summaries:
        totals["net_total"] += s.get("net_total", 0) or 0
        totals["gross_total"] += s.get("gross_total", 0) or 0
        totals["covers"] += s.get("covers", 0) or 0
        totals["discount"] += s.get("discount", 0) or 0

    return totals


def get_summaries_for_month_multi(location_ids: List[int], year: int, month: int) -> List[Dict]:
    """Get daily summaries for a specific month across multiple locations."""
    start_date, exclusive_end_date = month_bounds(year, month)
    end_date = _inclusive_end_from_exclusive(exclusive_end_date)

    return get_summaries_for_date_range_multi(location_ids, start_date, end_date)


def get_most_recent_date_with_data(location_ids: List[int]) -> Optional[str]:
    """Get the most recent date that has data."""
    import database

    if database.use_supabase():
        supabase = database.get_supabase_client()
        result = _execute_with_retry(
            supabase.table(SUPABASE_DAILY_SUMMARY)
            .select("date")
            .in_("location_id", location_ids)
            .order("date", desc=True)
            .limit(1)
        )
        if not result.data:
            return None
        return result.data[0]["date"]
    else:
        tbl = _sqlite_daily_table()
        with database.db_connection() as conn:
            cursor = conn.cursor()
            placeholders = ",".join("?" * len(location_ids))
            cursor.execute(
                f"""
                SELECT date FROM {tbl}
                WHERE location_id IN ({placeholders})
                ORDER BY date DESC LIMIT 1
                """,
                tuple(location_ids),
            )
            row = cursor.fetchone()
        return row["date"] if row else None


@st.cache_data(ttl=600)
def get_recent_summaries(location_id: int, weeks: int = 8) -> List[Dict]:
    """Get summaries for the most recent N weeks."""
    import database

    if database.use_supabase():
        supabase = database.get_supabase_client()
        result = _execute_with_retry(
            supabase.table(SUPABASE_DAILY_SUMMARY)
            .select("*")
            .eq("location_id", location_id)
            .order("date", desc=True)
            .limit(weeks * 7)
        )
        return _normalize_rows(result.data)
    else:
        tbl = _sqlite_daily_table()
        with database.db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"""
                SELECT * FROM {tbl}
                WHERE location_id = ?
                ORDER BY date DESC LIMIT ?
                """,
                (location_id, weeks * 7),
            )
            rows = cursor.fetchall()
        return [dict(row) for row in rows]


def get_location_settings(location_id: int) -> Optional[Dict]:
    """Get settings for a location."""
    locations = get_all_locations()
    for loc in locations:
        if loc["id"] == location_id:
            return loc
    return None


def get_upload_history(location_id: int, limit: int = 50) -> List[Dict]:
    """Get upload history for a location."""
    import database

    if database.use_supabase():
        supabase = database.get_supabase_client()
        result = _execute_with_retry(
            supabase.table("upload_history")
            .select("*")
            .eq("location_id", location_id)
            .order("uploaded_at", desc=True)
            .limit(limit)
        )
        return result.data
    else:
        with database.db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM upload_history
                WHERE location_id = ?
                ORDER BY uploaded_at DESC LIMIT ?
                """,
                (location_id, limit),
            )
            rows = cursor.fetchall()
        return [dict(row) for row in rows]


def get_all_summaries_for_export(
    location_ids: Optional[List[int]] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> List[Dict]:
    """Return daily summary rows for CSV/Excel export."""
    import database

    if database.use_supabase():
        supabase = database.get_supabase_client()

        location_map = {
            loc["id"]: loc["name"]
            for loc in _execute_with_retry(supabase.table("locations").select("id,name")).data
        }

        query = supabase.table(SUPABASE_DAILY_SUMMARY).select("*")

        if location_ids:
            query = query.in_("location_id", location_ids)
        if start_date:
            query = query.gte("date", start_date)
        if end_date:
            query = query.lte("date", end_date)

        result = _execute_with_retry(query.order("date"))
        rows = list(result.data or [])
    else:
        tbl = _sqlite_daily_table()
        with database.db_connection() as conn:
            cursor = conn.cursor()
            sql = f"SELECT * FROM {tbl} WHERE 1=1"
            params: list = []

            if location_ids:
                placeholders = ",".join("?" * len(location_ids))
                sql += f" AND location_id IN ({placeholders})"
                params.extend(location_ids)

            if start_date:
                sql += " AND date >= ?"
                params.append(start_date)

            if end_date:
                sql += " AND date <= ?"
                params.append(end_date)

            sql += " ORDER BY date"

            cursor.execute(sql, params)
            rows = [dict(row) for row in cursor.fetchall()]
        location_map = {loc["id"]: loc["name"] for loc in get_all_locations()}

    if start_date and end_date:
        scope_ids = list(location_ids) if location_ids else list(location_map.keys())
        rows = _apply_overrides_range(rows, scope_ids, start_date, end_date)

    for row in rows:
        if "location" not in row or not row.get("location"):
            row["location"] = location_map.get(row.get("location_id"), "")

    return rows


def clear_location_cache(location_id: int) -> None:
    """Clear all @st.cache_data caches for a specific location.

    Called after successful upload to ensure subsequent reads
    reflect the new data immediately.
    """
    get_all_locations.clear()
    get_summaries_for_month.clear()
    get_category_mtd_totals.clear()
    get_recent_summaries.clear()
