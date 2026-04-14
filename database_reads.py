"""Read/query operations for the new simplified database schema."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
import streamlit as st
import database


@st.cache_data(ttl=600)
def get_all_locations() -> List[Dict]:
    """Get all locations."""
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
        with database.db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT net_total FROM daily_summary
                WHERE location_id = ? AND date = ?
                """,
                (location_id, date),
            )
            row = cursor.fetchone()
        if not row:
            return None
        return float(row["net_total"] or 0)


def get_daily_summary(location_id: int, date: str) -> Optional[Dict]:
    """Get daily summary for a specific date."""
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
        return result.data[0]
    else:
        with database.db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM daily_summary WHERE location_id = ? AND date = ?",
                (location_id, date),
            )
            row = cursor.fetchone()
        return dict(row) if row else None


def get_summaries_for_date_range(
    location_id: int,
    start_date: str,
    end_date: str,
) -> List[Dict]:
    """Get daily summaries for a date range."""
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
        with database.db_connection() as conn:
            cursor = conn.cursor()
            placeholders = ",".join("?" * len(location_ids))
            cursor.execute(
                f"""
                SELECT * FROM daily_summary 
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
        with database.db_connection() as conn:
            cursor = conn.cursor()
            placeholders = ",".join("?" * len(location_ids))
            cursor.execute(
                f"""
                SELECT * FROM category_summary 
                WHERE location_id IN ({placeholders}) AND date >= ? AND date <= ?
                """,
                (*location_ids, start_date, end_date),
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
        with database.db_connection() as conn:
            cursor = conn.cursor()
            placeholders = ",".join("?" * len(location_ids))
            cursor.execute(
                f"""
                SELECT date FROM daily_summary 
                WHERE location_id IN ({placeholders})
                ORDER BY date DESC LIMIT 1
                """,
                tuple(location_ids),
            )
            row = cursor.fetchone()
        return row["date"] if row else None


def get_recent_summaries(location_id: int, weeks: int = 8) -> List[Dict]:
    """Get summaries for the most recent N weeks."""
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
    if database.use_supabase():
        supabase = database.get_supabase_client()
        result = (
            supabase.table("upload_history")
            .select("*")
            .order("uploaded_at", desc=True)
            .limit(limit)
            .execute()
        )
        return result.data
    else:
        with database.db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM upload_history ORDER BY uploaded_at DESC LIMIT ?",
                (limit,),
            )
            rows = cursor.fetchall()
        return [dict(row) for row in rows]


def get_all_summaries_for_export(
    location_ids: Optional[List[int]] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> List[Dict]:
    """Return daily summary rows for CSV/Excel export."""
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
        with database.db_connection() as conn:
            cursor = conn.cursor()
            sql = "SELECT * FROM daily_summary WHERE 1=1"
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
