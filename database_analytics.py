"""Analytics/read query helpers for database module.

This module keeps heavy reporting SQL separate from core write/auth operations.
"""

from __future__ import annotations

from typing import Any, Dict, List

import streamlit as st

import database


@st.cache_data(ttl=600)
def get_monthly_footfall_multi(
    location_ids: List[int], start_date: str, end_date: str
) -> List[Dict[str, Any]]:
    """Aggregate covers by month across locations for a date range."""
    if not location_ids:
        return []

    if database.use_supabase():
        supabase = database.get_supabase_client()
        result = supabase.rpc(
            "get_monthly_footfall_multi",
            {"loc_ids": location_ids, "start_dt": start_date, "end_dt": end_date},
        ).execute()
        return result.data
    else:
        with database.db_connection() as conn:
            cursor = conn.cursor()
            placeholders = ",".join("?" * len(location_ids))
            cursor.execute(
                f"""
                SELECT
                    month,
                    SUM(covers) AS covers,
                    CAST(
                        STRFTIME(
                            '%d',
                            CASE
                                WHEN month = SUBSTR(?, 1, 7)
                                    THEN ?
                                ELSE DATE(month || '-01', 'start of month', '+1 month', '-1 day')
                            END
                        ) AS INTEGER
                    ) AS total_days
                FROM (
                    SELECT SUBSTR(date, 1, 7) AS month, covers
                    FROM daily_summaries
                    WHERE location_id IN ({placeholders})
                      AND date >= ?
                      AND date <= ?
                ) m
                GROUP BY month
                ORDER BY month
                """,
                (end_date, end_date, *location_ids, start_date, end_date),
            )
            rows = cursor.fetchall()
        return [dict(row) for row in rows]


@st.cache_data(ttl=600)
def get_weekly_footfall_multi(
    location_ids: List[int], start_date: str, end_date: str
) -> List[Dict[str, Any]]:
    """Aggregate covers by ISO week across locations for a date range."""
    if not location_ids:
        return []

    if database.use_supabase():
        supabase = database.get_supabase_client()
        result = supabase.rpc(
            "get_weekly_footfall_multi",
            {"loc_ids": location_ids, "start_dt": start_date, "end_dt": end_date},
        ).execute()
        return result.data
    else:
        with database.db_connection() as conn:
            cursor = conn.cursor()
            placeholders = ",".join("?" * len(location_ids))
            cursor.execute(
                f"""
                WITH week_data AS (
                    SELECT
                        date,
                        covers,
                        date(date, '-' || ((strftime('%w', date) + 6) % 7) || ' days') AS iso_monday
                    FROM daily_summaries
                    WHERE location_id IN ({placeholders})
                      AND date >= ?
                      AND date <= ?
                )
                SELECT
                    CAST(strftime('%Y', date(iso_monday, '+3 days')) AS TEXT) || '-W' ||
                    printf('%02d', CAST(strftime('%W', date(iso_monday, '+3 days')) AS INTEGER) + 1) AS week,
                    SUM(covers) AS covers,
                    CAST(COUNT(DISTINCT date) AS INTEGER) AS total_days
                FROM week_data
                GROUP BY week
                ORDER BY week
                """,
                (*location_ids, start_date, end_date),
            )
            rows = cursor.fetchall()
        return [dict(row) for row in rows]


@st.cache_data(ttl=300)
def get_category_mtd_totals_multi(
    location_ids: List[int], year: int, month: int
) -> Dict[str, float]:
    """Sum category totals for month across multiple locations."""
    if not location_ids:
        return {}

    start_date = f"{year}-{month:02d}-01"
    if month == 12:
        end_date = f"{year + 1}-01-01"
    else:
        end_date = f"{year}-{month + 1:02d}-01"

    if database.use_supabase():
        supabase = database.get_supabase_client()
        result = supabase.rpc(
            "get_category_mtd_totals_multi",
            {"loc_ids": location_ids, "start_dt": start_date, "end_dt": end_date},
        ).execute()
        return {row["category"]: float(row["total"] or 0) for row in result.data}
    else:
        placeholders = ",".join("?" * len(location_ids))
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
            rows = cursor.fetchall()
        return {row["category"]: float(row["total"] or 0) for row in rows}


@st.cache_data(ttl=300)
def get_service_mtd_totals_multi(
    location_ids: List[int], year: int, month: int
) -> Dict[str, float]:
    """Sum service totals for month across multiple locations."""
    if not location_ids:
        return {}

    start_date = f"{year}-{month:02d}-01"
    if month == 12:
        end_date = f"{year + 1}-01-01"
    else:
        end_date = f"{year}-{month + 1:02d}-01"

    if database.use_supabase():
        supabase = database.get_supabase_client()
        result = supabase.rpc(
            "get_service_mtd_totals_multi",
            {"loc_ids": location_ids, "start_dt": start_date, "end_dt": end_date},
        ).execute()
        return {row["service_type"]: float(row["total"] or 0) for row in result.data}
    else:
        placeholders = ",".join("?" * len(location_ids))
        with database.db_connection() as conn:
            cursor = conn.cursor()
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
            rows = cursor.fetchall()
        return {row["service_type"]: float(row["total"] or 0) for row in rows}


@st.cache_data(ttl=300)
def get_top_items_for_date_range(
    location_ids: List[int], start_date: str, end_date: str, limit: int = 20
) -> List[Dict]:
    """Top-selling menu items for one or more locations within date range."""
    if not location_ids:
        return []

    if database.use_supabase():
        supabase = database.get_supabase_client()
        result = supabase.rpc(
            "get_top_items_for_date_range",
            {
                "loc_ids": location_ids,
                "start_dt": start_date,
                "end_dt": end_date,
                "lim": limit,
            },
        ).execute()
        return result.data
    else:
        placeholders = ",".join("?" * len(location_ids))
        with database.db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"""
                WITH filtered_days AS (
                    SELECT id
                    FROM daily_summaries
                    WHERE location_id IN ({placeholders})
                      AND date BETWEEN ? AND ?
                )
                SELECT it.item_name,
                       SUM(it.amount) AS amount,
                       SUM(it.qty)    AS qty
                FROM item_sales it
                JOIN filtered_days ds ON it.summary_id = ds.id
                GROUP BY it.item_name
                ORDER BY amount DESC
                LIMIT ?
                """,
                (*location_ids, start_date, end_date, limit),
            )
            rows = cursor.fetchall()
        return [dict(row) for row in rows]


@st.cache_data(ttl=120)
def get_category_sales_for_date_range(
    location_ids: List[int], start_date: str, end_date: str
) -> List[Dict]:
    """Aggregate category sales across locations for a date range."""
    if not location_ids:
        return []

    if database.use_supabase():
        supabase = database.get_supabase_client()
        result = supabase.rpc(
            "get_category_sales_for_date_range",
            {"loc_ids": location_ids, "start_dt": start_date, "end_dt": end_date},
        ).execute()
        return result.data
    else:
        placeholders = ",".join("?" * len(location_ids))
        with database.db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"""
                WITH filtered_days AS (
                    SELECT id
                    FROM daily_summaries
                    WHERE location_id IN ({placeholders})
                      AND date BETWEEN ? AND ?
                )
                SELECT cs.category,
                       SUM(cs.amount) AS amount,
                       SUM(cs.qty)    AS qty
                FROM category_sales cs
                JOIN filtered_days ds ON cs.summary_id = ds.id
                GROUP BY cs.category
                ORDER BY amount DESC
                """,
                (*location_ids, start_date, end_date),
            )
            rows = cursor.fetchall()
        return [dict(row) for row in rows]


@st.cache_data(ttl=120)
def get_service_sales_for_date_range(
    location_ids: List[int], start_date: str, end_date: str
) -> List[Dict]:
    """Aggregate service sales across locations for a date range."""
    if not location_ids:
        return []

    if database.use_supabase():
        supabase = database.get_supabase_client()
        result = supabase.rpc(
            "get_service_sales_for_date_range",
            {"loc_ids": location_ids, "start_dt": start_date, "end_dt": end_date},
        ).execute()
        return result.data
    else:
        placeholders = ",".join("?" * len(location_ids))
        with database.db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"""
                WITH filtered_days AS (
                    SELECT id
                    FROM daily_summaries
                    WHERE location_id IN ({placeholders})
                      AND date BETWEEN ? AND ?
                )
                SELECT ss.service_type,
                       SUM(ss.amount) AS amount
                FROM service_sales ss
                JOIN filtered_days ds ON ss.summary_id = ds.id
                GROUP BY ss.service_type
                ORDER BY amount DESC
                """,
                (*location_ids, start_date, end_date),
            )
            rows = cursor.fetchall()
        return [dict(row) for row in rows]


@st.cache_data(ttl=300)
def get_daily_service_sales_for_date_range(
    location_ids: List[int], start_date: str, end_date: str
) -> List[Dict]:
    """Per-day service totals for stacked charts."""
    if not location_ids:
        return []

    if database.use_supabase():
        supabase = database.get_supabase_client()
        result = supabase.rpc(
            "get_daily_service_sales_for_date_range",
            {"loc_ids": location_ids, "start_dt": start_date, "end_dt": end_date},
        ).execute()
        return result.data
    else:
        placeholders = ",".join("?" * len(location_ids))
        with database.db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"""
                WITH filtered_days AS (
                    SELECT id, date
                    FROM daily_summaries
                    WHERE location_id IN ({placeholders})
                      AND date BETWEEN ? AND ?
                )
                SELECT ds.date,
                       ss.service_type,
                       SUM(ss.amount) AS amount
                FROM service_sales ss
                JOIN filtered_days ds ON ss.summary_id = ds.id
                GROUP BY ds.date, ss.service_type
                ORDER BY ds.date, ss.service_type
                """,
                (*location_ids, start_date, end_date),
            )
            rows = cursor.fetchall()
        return [dict(row) for row in rows]


@st.cache_data(ttl=300)
def get_super_category_mtd_totals(
    location_id: int, year: int, month: int
) -> Dict[str, float]:
    start_date = f"{year}-{month:02d}-01"
    end_date = f"{year + 1}-01-01" if month == 12 else f"{year}-{month + 1:02d}-01"
    with database.db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """SELECT scs.category, SUM(scs.amount) AS total, SUM(scs.qty) AS total_qty
            FROM super_category_sales scs
            INNER JOIN daily_summaries ds ON scs.summary_id = ds.id
            WHERE ds.location_id = ? AND ds.date >= ? AND ds.date < ?
            GROUP BY scs.category""",
            (location_id, start_date, end_date),
        )
        rows = cursor.fetchall()
    return {row["category"]: float(row["total"] or 0) for row in rows}


@st.cache_data(ttl=300)
def get_super_category_mtd_totals_multi(
    location_ids: List[int], year: int, month: int
) -> Dict[str, float]:
    if not location_ids:
        return {}
    start_date = f"{year}-{month:02d}-01"
    end_date = f"{year + 1}-01-01" if month == 12 else f"{year}-{month + 1:02d}-01"
    ph = ",".join("?" * len(location_ids))
    with database.db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            f"""SELECT scs.category, SUM(scs.amount) AS total, SUM(scs.qty) AS total_qty
            FROM super_category_sales scs
            INNER JOIN daily_summaries ds ON scs.summary_id = ds.id
            WHERE ds.location_id IN ({ph}) AND ds.date >= ? AND ds.date < ?
            GROUP BY scs.category""",
            (*location_ids, start_date, end_date),
        )
        rows = cursor.fetchall()
    return {row["category"]: float(row["total"] or 0) for row in rows}


@st.cache_data(ttl=120)
def get_super_category_sales_for_date_range(
    location_ids: List[int], start_date: str, end_date: str
) -> List[Dict]:
    if not location_ids:
        return []
    ph = ",".join("?" * len(location_ids))
    with database.db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            f"""WITH filtered_days AS (
                SELECT id FROM daily_summaries
                WHERE location_id IN ({ph}) AND date BETWEEN ? AND ?
            ) SELECT scs.category, SUM(scs.amount) AS amount, SUM(scs.qty) AS qty
            FROM super_category_sales scs
            JOIN filtered_days ds ON scs.summary_id = ds.id
            GROUP BY scs.category ORDER BY amount DESC""",
            (*location_ids, start_date, end_date),
        )
        rows = cursor.fetchall()
    return [dict(row) for row in rows]


@st.cache_data(ttl=120)
def get_item_sales_for_date_range(
    location_ids: List[int], start_date: str, end_date: str, limit: int = 30
) -> List[Dict]:
    if not location_ids:
        return []
    ph = ",".join("?" * len(location_ids))
    with database.db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            f"""WITH filtered_days AS (
                SELECT id FROM daily_summaries
                WHERE location_id IN ({ph}) AND date BETWEEN ? AND ?
            ) SELECT iss.item_name, iss.category, SUM(iss.qty) AS qty, SUM(iss.amount) AS amount
            FROM item_sales iss JOIN filtered_days ds ON iss.summary_id = ds.id
            GROUP BY iss.item_name, iss.category ORDER BY qty DESC LIMIT ?""",
            (*location_ids, start_date, end_date, limit),
        )
        rows = cursor.fetchall()
    return [dict(row) for row in rows]
