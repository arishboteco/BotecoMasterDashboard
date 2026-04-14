"""Read/query operations for the new simplified database schema."""

from __future__ import annotations

from typing import Dict, List, Optional

import streamlit as st

# Must match database_writes._CATEGORY_ROW_PREFIX (avoid importing database_writes here).
_CATEGORY_ROW_PREFIX = "__category_row:"


def _sqlite_daily_table() -> str:
    """Legacy local schema table name (Supabase uses singular daily_summary)."""
    return "daily_summaries"


def _sqlite_categories_for_summary(conn, summary_id: int) -> List[Dict]:
    """Rebuild category aggregates saved with synthetic item_sales rows."""
    cur = conn.cursor()
    cur.execute(
        f"""
        SELECT category, qty, amount
        FROM item_sales
        WHERE summary_id = ?
          AND item_name LIKE ?
        """,
        (summary_id, f"{_CATEGORY_ROW_PREFIX}%"),
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
        """
        SELECT service_type, amount
        FROM service_sales
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
        result = supabase.table("locations").select("*").order("name").execute()
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
        result = (
            supabase.table("daily_summary")
            .select("net_total")
            .eq("location_id", location_id)
            .eq("date", date)
            .execute()
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


def _detail_lists_for_daily_summary(
    location_id: int, date: str
) -> tuple[List[Dict], List[Dict]]:
    """Build categories + services lists for PNG/report bundle (Supabase schema).

    daily_summary rows do not embed these; they live in category_summary and are
    derived for services from bill_items.
    """
    from database_analytics import (
        get_category_sales_for_date_range,
        get_service_sales_for_date_range,
    )

    cats_out: List[Dict] = []
    cat_rows = get_category_sales_for_date_range(
        [location_id], date, date
    )
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
        result = (
            supabase.table("daily_summary")
            .select("*")
            .eq("location_id", location_id)
            .eq("date", date)
            .execute()
        )
        if not result.data:
            return None
        d = dict(result.data[0])
        try:
            cats, svcs = _detail_lists_for_daily_summary(location_id, date)
            d["categories"] = cats
            d["services"] = svcs
        except Exception:
            d.setdefault("categories", [])
            d.setdefault("services", [])
        return d
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
                return None
            d = dict(row)
            sid = int(d["id"])
            d["categories"] = _sqlite_categories_for_summary(conn, sid)
            d["services"] = _sqlite_services_for_summary(conn, sid)
            if not d["services"]:
                try:
                    from database_analytics import get_service_sales_for_date_range

                    svcs = get_service_sales_for_date_range(
                        [location_id], date, date
                    )
                    d["services"] = [
                        {
                            "type": str(
                                s.get("type") or s.get("service_type") or ""
                            ),
                            "amount": float(s.get("amount") or 0),
                        }
                        for s in (svcs or [])
                        if float(s.get("amount") or 0) > 0
                    ]
                except Exception:
                    pass
        return d


def get_summaries_for_date_range(
    location_id: int,
    start_date: str,
    end_date: str,
) -> List[Dict]:
    """Get daily summaries for a date range."""
    import database

    if database.use_supabase():
        supabase = database.get_supabase_client()
        result = (
            supabase.table("daily_summary")
            .select("*")
            .eq("location_id", location_id)
            .gte("date", start_date)
            .lte("date", end_date)
            .order("date")
            .execute()
        )
        return result.data
    else:
        with database.db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM daily_summary 
                WHERE location_id = ? AND date >= ? AND date <= ?
                ORDER BY date
                """,
                (location_id, start_date, end_date),
            )
            rows = cursor.fetchall()
        return [dict(row) for row in rows]


def get_summaries_for_month(location_id: int, year: int, month: int) -> List[Dict]:
    """Get daily summaries for a specific month."""
    start_date = f"{year}-{month:02d}-01"
    if month == 12:
        end_date = f"{year + 1}-01-01"
    else:
        end_date = f"{year}-{month + 1:02d}-01"

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
        result = (
            supabase.table("daily_summary")
            .select("*")
            .in_("location_id", location_ids)
            .gte("date", start_date)
            .lte("date", end_date)
            .order("date")
            .execute()
        )
        return result.data
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
            rows = cursor.fetchall()
        return [dict(row) for row in rows]


def get_category_totals_for_date_range(
    location_ids: List[int],
    start_date: str,
    end_date: str,
) -> List[Dict]:
    """Get category totals for a date range."""
    import database

    if database.use_supabase():
        supabase = database.get_supabase_client()
        result = (
            supabase.table("category_summary")
            .select("*")
            .in_("location_id", location_ids)
            .gte("date", start_date)
            .lte("date", end_date)
            .execute()
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
                FROM item_sales i
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
                    f"{_CATEGORY_ROW_PREFIX}%",
                ),
            )
            rows = cursor.fetchall()
        return [dict(row) for row in rows]


def get_category_mtd_totals(
    location_ids: List[int],
    year: int,
    month: int,
) -> List[Dict]:
    """Get category totals for month-to-date."""
    start_date = f"{year}-{month:02d}-01"
    return get_category_totals_for_date_range(location_ids, start_date, "2999-12-31")


def get_mtd_totals_multi(
    location_ids: List[int], year: int, month: int
) -> Dict[str, float]:
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


def get_summaries_for_month_multi(
    location_ids: List[int], year: int, month: int
) -> List[Dict]:
    """Get daily summaries for a specific month across multiple locations."""
    start_date = f"{year}-{month:02d}-01"
    if month == 12:
        end_date = f"{year + 1}-01-01"
    else:
        end_date = f"{year}-{month + 1:02d}-01"

    return get_summaries_for_date_range_multi(location_ids, start_date, end_date)


def get_most_recent_date_with_data(location_ids: List[int]) -> Optional[str]:
    """Get the most recent date that has data."""
    import database

    if database.use_supabase():
        supabase = database.get_supabase_client()
        result = (
            supabase.table("daily_summary")
            .select("date")
            .in_("location_id", location_ids)
            .order("date", desc=True)
            .limit(1)
            .execute()
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


def get_recent_summaries(location_id: int, weeks: int = 8) -> List[Dict]:
    """Get summaries for the most recent N weeks."""
    import database

    if database.use_supabase():
        supabase = database.get_supabase_client()
        result = (
            supabase.table("daily_summary")
            .select("*")
            .eq("location_id", location_id)
            .order("date", desc=True)
            .limit(weeks * 7)
            .execute()
        )
        return result.data
    else:
        with database.db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM daily_summary 
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
        result = (
            supabase.table("upload_history")
            .select("*")
            .eq("location_id", location_id)
            .order("uploaded_at", desc=True)
            .limit(limit)
            .execute()
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
            for loc in supabase.table("locations").select("id,name").execute().data
        }

        query = supabase.table("daily_summary").select("*")

        if location_ids:
            query = query.in_("location_id", location_ids)
        if start_date:
            query = query.gte("date", start_date)
        if end_date:
            query = query.lte("date", end_date)

        result = query.order("date").execute()

        for row in result.data:
            row["location"] = location_map.get(row["location_id"], "")

        return result.data
    else:
        tbl = _sqlite_daily_table()
        with database.db_connection() as conn:
            cursor = conn.cursor()
            sql = f"SELECT * FROM {tbl} WHERE 1=1"
            params = []

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
            return [dict(row) for row in cursor.fetchall()]


def clear_location_cache(location_id: int) -> None:
    """Clear all @st.cache_data caches for a specific location.

    Called after successful upload to ensure subsequent reads
    reflect the new data immediately.
    """
    get_all_locations.clear()
    get_summaries_for_month.clear(location_id=location_id)
    get_category_mtd_totals.clear(location_id=location_id)
    get_recent_summaries.clear(location_id=location_id)
