"""Read/query operations for the database layer."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import streamlit as st

import database


def get_all_locations() -> List[Dict]:
    """Get all locations."""
    with database.db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM locations ORDER BY name")
        rows = cursor.fetchall()
    return [dict(row) for row in rows]


def peek_daily_net_sales(location_id: int, date: str) -> Optional[float]:
    """Return saved net_total for a day if a row exists."""
    with database.db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT net_total FROM daily_summaries
            WHERE location_id = ? AND date = ?
            """,
            (location_id, date),
        )
        row = cursor.fetchone()
    if not row:
        return None
    return float(row["net_total"] or 0)


def get_all_summaries_for_export(
    location_ids: Optional[List[int]] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> List[Dict]:
    """Return daily summary rows (with location name) for CSV/Excel export."""
    with database.db_connection() as conn:
        cursor = conn.cursor()

        conditions = []
        params: List[Any] = []

        if location_ids:
            placeholders = ",".join("?" * len(location_ids))
            conditions.append(f"ds.location_id IN ({placeholders})")
            params.extend(location_ids)
        if start_date:
            conditions.append("ds.date >= ?")
            params.append(start_date)
        if end_date:
            conditions.append("ds.date <= ?")
            params.append(end_date)

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        cursor.execute(
            f"""
            SELECT
                l.name            AS outlet,
                ds.date,
                ds.covers,
                ds.order_count,
                ds.gross_total,
                ds.net_total,
                ds.cash_sales,
                ds.card_sales,
                ds.gpay_sales,
                ds.zomato_sales,
                ds.other_sales,
                ds.discount,
                ds.complimentary,
                ds.service_charge,
                ds.cgst,
                ds.sgst,
                ds.apc,
                ds.turns,
                ds.target,
                ds.pct_target,
                ds.lunch_covers,
                ds.dinner_covers,
                ds.mtd_net_sales,
                ds.mtd_total_covers,
                ds.mtd_avg_daily,
                ds.mtd_target,
                ds.mtd_pct_target
            FROM daily_summaries ds
            JOIN locations l ON ds.location_id = l.id
            {where}
            ORDER BY ds.date DESC, l.name
            """,
            params,
        )
        rows = cursor.fetchall()
    return [dict(row) for row in rows]


def get_daily_summary(location_id: int, date: str) -> Optional[Dict]:
    """Get daily summary for a specific date."""
    with database.db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT * FROM daily_summaries
            WHERE location_id = ? AND date = ?
            """,
            (location_id, date),
        )
        row = cursor.fetchone()

        if row:
            summary = dict(row)
            cursor.execute(
                "SELECT * FROM category_sales WHERE summary_id = ?", (summary["id"],)
            )
            summary["categories"] = [dict(r) for r in cursor.fetchall()]
            cursor.execute(
                "SELECT * FROM service_sales WHERE summary_id = ?", (summary["id"],)
            )
            summary["services"] = [dict(r) for r in cursor.fetchall()]
            return summary

    return None


@st.cache_data(ttl=300)
def get_summaries_for_month(location_id: int, year: int, month: int) -> List[Dict]:
    """Get all summaries for a specific month."""
    start_date = f"{year}-{month:02d}-01"
    if month == 12:
        end_date = f"{year + 1}-01-01"
    else:
        end_date = f"{year}-{month + 1:02d}-01"

    with database.db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT * FROM daily_summaries
            WHERE location_id = ? AND date >= ? AND date < ?
            ORDER BY date
            """,
            (location_id, start_date, end_date),
        )
        rows = cursor.fetchall()
    return [dict(row) for row in rows]


@st.cache_data(ttl=300)
def get_category_mtd_totals(
    location_id: int, year: int, month: int
) -> Dict[str, float]:
    """Sum category sales amounts for calendar month."""
    start_date = f"{year}-{month:02d}-01"
    if month == 12:
        end_date = f"{year + 1}-01-01"
    else:
        end_date = f"{year}-{month + 1:02d}-01"
    with database.db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT cs.category, SUM(cs.amount) AS total
            FROM category_sales cs
            INNER JOIN daily_summaries ds ON cs.summary_id = ds.id
            WHERE ds.location_id = ? AND ds.date >= ? AND ds.date < ?
            GROUP BY cs.category
            """,
            (location_id, start_date, end_date),
        )
        rows = cursor.fetchall()
    return {row["category"]: float(row["total"] or 0) for row in rows}


@st.cache_data(ttl=300)
def get_service_mtd_totals(location_id: int, year: int, month: int) -> Dict[str, float]:
    """Sum service sales amounts for calendar month."""
    start_date = f"{year}-{month:02d}-01"
    if month == 12:
        end_date = f"{year + 1}-01-01"
    else:
        end_date = f"{year}-{month + 1:02d}-01"
    with database.db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT sv.service_type, SUM(sv.amount) AS total
            FROM service_sales sv
            INNER JOIN daily_summaries ds ON sv.summary_id = ds.id
            WHERE ds.location_id = ? AND ds.date >= ? AND ds.date < ?
            GROUP BY sv.service_type
            """,
            (location_id, start_date, end_date),
        )
        rows = cursor.fetchall()
    return {row["service_type"]: float(row["total"] or 0) for row in rows}


@st.cache_data(ttl=120)
def get_summaries_for_date_range(
    location_id: int, start_date: str, end_date: str
) -> List[Dict]:
    """Get summaries for a date range."""
    with database.db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT * FROM daily_summaries
            WHERE location_id = ? AND date >= ? AND date <= ?
            ORDER BY date
            """,
            (location_id, start_date, end_date),
        )
        rows = cursor.fetchall()
    return [dict(row) for row in rows]


@st.cache_data(ttl=120)
def get_summaries_for_date_range_multi(
    location_ids: List[int], start_date: str, end_date: str
) -> List[Dict]:
    """All summaries in range for multiple locations (not merged by date)."""
    if not location_ids:
        return []
    placeholders = ",".join("?" * len(location_ids))
    with database.db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            f"""
            SELECT * FROM daily_summaries
            WHERE location_id IN ({placeholders}) AND date >= ? AND date <= ?
            ORDER BY date, location_id
            """,
            (*location_ids, start_date, end_date),
        )
        rows = cursor.fetchall()
    return [dict(row) for row in rows]


@st.cache_data(ttl=300)
def get_mtd_totals_multi(
    location_ids: List[int], year: int, month: int
) -> Tuple[Dict[str, float], Dict[str, float]]:
    """Fetch both category and service MTD totals across multiple locations in one query.

    Returns (category_totals, service_totals).
    """
    if not location_ids:
        return {}, {}
    placeholders = ",".join("?" * len(location_ids))
    start_date = f"{year}-{month:02d}-01"
    if month == 12:
        end_date = f"{year + 1}-01-01"
    else:
        end_date = f"{year}-{month + 1:02d}-01"

    with database.db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            f"""
            SELECT cs.category, SUM(cs.amount) AS total
            FROM category_sales cs
            INNER JOIN daily_summaries ds ON cs.summary_id = ds.id
            WHERE ds.location_id IN ({placeholders}) AND ds.date >= ? AND ds.date < ?
            GROUP BY cs.category
            """,
            (*location_ids, start_date, end_date),
        )
        cat_rows = cursor.fetchall()
        cursor.execute(
            f"""
            SELECT sv.service_type, SUM(sv.amount) AS total
            FROM service_sales sv
            INNER JOIN daily_summaries ds ON sv.summary_id = ds.id
            WHERE ds.location_id IN ({placeholders}) AND ds.date >= ? AND ds.date < ?
            GROUP BY sv.service_type
            """,
            (*location_ids, start_date, end_date),
        )
        svc_rows = cursor.fetchall()

    cat_totals = {row["category"]: float(row["total"] or 0) for row in cat_rows}
    svc_totals = {row["service_type"]: float(row["total"] or 0) for row in svc_rows}
    return cat_totals, svc_totals


@st.cache_data(ttl=300)
def get_summaries_for_month_multi(
    location_ids: List[int], year: int, month: int
) -> List[Dict]:
    """Get all summaries for a specific month across multiple locations."""
    if not location_ids:
        return []
    placeholders = ",".join("?" * len(location_ids))
    start_date = f"{year}-{month:02d}-01"
    if month == 12:
        end_date = f"{year + 1}-01-01"
    else:
        end_date = f"{year}-{month + 1:02d}-01"
    with database.db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            f"""
            SELECT * FROM daily_summaries
            WHERE location_id IN ({placeholders}) AND date >= ? AND date < ?
            ORDER BY date
            """,
            (*location_ids, start_date, end_date),
        )
        rows = cursor.fetchall()
    return [dict(row) for row in rows]


def get_most_recent_date_with_data(location_ids: List[int]) -> Optional[str]:
    """Get most recent saved summary date across one or more locations."""
    if not location_ids:
        return None

    placeholders = ",".join("?" * len(location_ids))
    with database.db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            f"""
            SELECT MAX(date) AS most_recent_date
            FROM daily_summaries
            WHERE location_id IN ({placeholders})
            """,
            (*location_ids,),
        )
        row = cursor.fetchone()
    if row and row["most_recent_date"]:
        return str(row["most_recent_date"])
    return None


def get_location_settings(location_id: int) -> Optional[Dict]:
    """Get location settings."""
    with database.db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM locations WHERE id = ?", (location_id,))
        row = cursor.fetchone()
    return dict(row) if row else None


def get_upload_history(location_id: int, limit: int = 50) -> List[Dict]:
    """Get upload history."""
    with database.db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT * FROM upload_history
            WHERE location_id = ?
            ORDER BY uploaded_at DESC
            LIMIT ?
            """,
            (location_id, limit),
        )
        rows = cursor.fetchall()
    return [dict(row) for row in rows]


@st.cache_data(ttl=300)
def get_recent_summaries(location_id: int, weeks: int = 8) -> List[Dict]:
    """Fetch daily summaries for the last N weeks for a location.

    Returns rows with date, net_total — sufficient for weekday mix analysis.
    """
    with database.db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT date, net_total
            FROM daily_summaries
            WHERE location_id = ?
            ORDER BY date DESC
            LIMIT ?
            """,
            (location_id, weeks * 7),
        )
        rows = cursor.fetchall()
    return [dict(row) for row in rows]
