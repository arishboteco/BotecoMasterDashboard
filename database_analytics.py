"""Analytics/read query helpers for database module.

This module keeps heavy reporting SQL separate from core write/auth operations.
Uses the new simplified schema.
"""

from __future__ import annotations

from typing import Any, Dict, List, Set

import streamlit as st


def _bill_items_success(status: Any) -> bool:
    """Match Petpooja / CSV bill status (case-insensitive)."""
    s = str(status or "").strip().lower()
    return s in ("", "successorder")


def _restaurants_for_location_ids(location_ids: List[int]) -> List[str]:
    """Map outlet ids to Dynamic Report restaurant names on bill_items."""
    from database_writes import LOCATION_ID_TO_RESTAURANT

    return [LOCATION_ID_TO_RESTAURANT.get(int(lid), "Boteco") for lid in location_ids]


@st.cache_data(ttl=600)
def get_monthly_footfall_multi(
    location_ids: List[int], start_date: str, end_date: str
) -> List[Dict[str, Any]]:
    """Aggregate covers by month across locations for a date range."""
    import database

    if not location_ids:
        return []

    if database.use_supabase():
        supabase = database.get_supabase_client()
        result = (
            supabase.table("daily_summary")
            .select("date,covers,net_total,gross_total")
            .in_("location_id", location_ids)
            .gte("date", start_date)
            .lte("date", end_date)
            .execute()
        )

        monthly = {}
        days_per_month: Dict[str, Set[str]] = {}
        for row in result.data:
            month = row["date"][:7]
            if month not in monthly:
                monthly[month] = {
                    "month": month,
                    "covers": 0,
                    "net_total": 0.0,
                    "gross_total": 0.0,
                }
                days_per_month[month] = set()
            monthly[month]["covers"] += row.get("covers", 0) or 0
            monthly[month]["net_total"] += row.get("net_total", 0) or 0
            monthly[month]["gross_total"] += row.get("gross_total", 0) or 0
            days_per_month[month].add(row["date"])

        out = []
        for m in sorted(monthly.keys()):
            row = dict(monthly[m])
            row["total_days"] = len(days_per_month.get(m, set()))
            out.append(row)
        return out
    else:
        with database.db_connection() as conn:
            cur = conn.cursor()
            placeholders = ",".join("?" * len(location_ids))
            cur.execute(
                f"""
                SELECT date, covers, net_total, gross_total
                FROM daily_summaries
                WHERE location_id IN ({placeholders})
                  AND date >= ? AND date <= ?
                ORDER BY date
                """,
                (*location_ids, start_date, end_date),
            )
            rows = cur.fetchall()
        monthly: Dict[str, Dict[str, Any]] = {}
        days_per_month: Dict[str, Set[str]] = {}
        for row in rows:
            d = str(row["date"])
            month = d[:7]
            if month not in monthly:
                monthly[month] = {
                    "month": month,
                    "covers": 0,
                    "net_total": 0.0,
                    "gross_total": 0.0,
                }
                days_per_month[month] = set()
            monthly[month]["covers"] += int(row["covers"] or 0)
            monthly[month]["net_total"] += float(row["net_total"] or 0)
            monthly[month]["gross_total"] += float(row["gross_total"] or 0)
            days_per_month[month].add(d)
        out = []
        for m in sorted(monthly.keys()):
            r = dict(monthly[m])
            r["total_days"] = len(days_per_month.get(m, set()))
            out.append(r)
        return out


@st.cache_data(ttl=600)
def get_weekly_footfall_multi(
    location_ids: List[int], start_date: str, end_date: str
) -> List[Dict[str, Any]]:
    """Aggregate covers by ISO week across locations for a date range."""
    import database

    if not location_ids:
        return []

    if database.use_supabase():
        supabase = database.get_supabase_client()
        result = (
            supabase.table("daily_summary")
            .select("date,covers,net_total")
            .in_("location_id", location_ids)
            .gte("date", start_date)
            .lte("date", end_date)
            .execute()
        )

        weekly = {}
        days_per_week: Dict[str, Set[str]] = {}
        for row in result.data:
            from datetime import datetime, timedelta

            date = datetime.strptime(row["date"], "%Y-%m-%d")
            monday = date - timedelta(days=date.weekday())
            week_key = monday.strftime("%Y-W%W")
            if week_key not in weekly:
                weekly[week_key] = {"week": week_key, "covers": 0, "net_total": 0.0}
                days_per_week[week_key] = set()
            weekly[week_key]["covers"] += row.get("covers", 0) or 0
            weekly[week_key]["net_total"] += row.get("net_total", 0) or 0
            days_per_week[week_key].add(row["date"])

        out = []
        for wk in sorted(weekly.keys()):
            r = dict(weekly[wk])
            r["total_days"] = len(days_per_week.get(wk, set()))
            out.append(r)
        return out
    else:
        if not location_ids:
            return []
        with database.db_connection() as conn:
            cur = conn.cursor()
            placeholders = ",".join("?" * len(location_ids))
            cur.execute(
                f"""
                SELECT date, covers, net_total
                FROM daily_summaries
                WHERE location_id IN ({placeholders})
                  AND date >= ? AND date <= ?
                ORDER BY date
                """,
                (*location_ids, start_date, end_date),
            )
            rows = cur.fetchall()
        weekly = {}
        days_per_week: Dict[str, Set[str]] = {}
        for row in rows:
            from datetime import datetime, timedelta

            date = datetime.strptime(str(row["date"]), "%Y-%m-%d")
            monday = date - timedelta(days=date.weekday())
            week_key = monday.strftime("%Y-W%W")
            if week_key not in weekly:
                weekly[week_key] = {"week": week_key, "covers": 0, "net_total": 0.0}
                days_per_week[week_key] = set()
            weekly[week_key]["covers"] += int(row["covers"] or 0)
            weekly[week_key]["net_total"] += float(row["net_total"] or 0)
            days_per_week[week_key].add(str(row["date"]))
        out = []
        for wk in sorted(weekly.keys()):
            r = dict(weekly[wk])
            r["total_days"] = len(days_per_week.get(wk, set()))
            out.append(r)
        return out


@st.cache_data(ttl=600)
def get_daily_sales_for_date_range(
    location_ids: List[int], start_date: str, end_date: str
) -> List[Dict[str, Any]]:
    """Get daily sales data for a date range."""
    import database

    if database.use_supabase():
        supabase = database.get_supabase_client()
        result = (
            supabase.table("daily_summary")
            .select("date,location_id,net_total,gross_total,covers,discount")
            .in_("location_id", location_ids)
            .gte("date", start_date)
            .lte("date", end_date)
            .order("date")
            .execute()
        )
        return result.data
    else:
        if not location_ids:
            return []
        with database.db_connection() as conn:
            cur = conn.cursor()
            placeholders = ",".join("?" * len(location_ids))
            cur.execute(
                f"""
                SELECT date, location_id, net_total, gross_total, covers, discount
                FROM daily_summaries
                WHERE location_id IN ({placeholders})
                  AND date >= ? AND date <= ?
                ORDER BY date
                """,
                (*location_ids, start_date, end_date),
            )
            rows = cur.fetchall()
        return [dict(r) for r in rows]


def get_category_sales_for_date_range(
    location_ids: List[int],
    start_date: str,
    end_date: str,
) -> List[Dict[str, Any]]:
    """Get category sales totals for a date range."""
    import database

    if database.use_supabase():
        supabase = database.get_supabase_client()
        result = (
            supabase.table("category_summary")
            .select("category_name,net_amount,qty")
            .in_("location_id", location_ids)
            .gte("date", start_date)
            .lte("date", end_date)
            .execute()
        )

        cat_totals = {}
        for row in result.data:
            cat = row["category_name"]
            if cat not in cat_totals:
                cat_totals[cat] = {"category": cat, "amount": 0.0, "qty": 0}
            cat_totals[cat]["amount"] += row.get("net_amount", 0) or 0
            cat_totals[cat]["qty"] += row.get("qty", 0) or 0

        return sorted(cat_totals.values(), key=lambda x: -x["amount"])
    else:
        from database_reads import get_category_totals_for_date_range

        rows = get_category_totals_for_date_range(
            location_ids, start_date, end_date
        )
        cat_totals: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            cat = row.get("category_name") or "Uncategorized"
            if cat not in cat_totals:
                cat_totals[cat] = {"category": cat, "amount": 0.0, "qty": 0}
            cat_totals[cat]["amount"] += float(row.get("net_amount", 0) or 0)
            cat_totals[cat]["qty"] += int(row.get("qty", 0) or 0)
        return sorted(cat_totals.values(), key=lambda x: -x["amount"])


def get_service_sales_for_date_range(
    location_ids: List[int],
    start_date: str,
    end_date: str,
) -> List[Dict[str, Any]]:
    """Get service period (Lunch/Dinner) sales from bill_items.

    Lunch: 12 PM - 5 PM (12:00 to 16:59)
    Dinner: Everything else
    """
    import database

    if database.use_supabase():
        supabase = database.get_supabase_client()
        restaurants = _restaurants_for_location_ids(location_ids)
        result = (
            supabase.table("bill_items")
            .select("created_date_time,net_amount,bill_status")
            .in_("restaurant", restaurants)
            .gte("bill_date", start_date)
            .lte("bill_date", end_date)
            .execute()
        )

        lunch_total = 0.0
        dinner_total = 0.0

        for row in result.data:
            if not _bill_items_success(row.get("bill_status")):
                continue
            net = row.get("net_amount", 0) or 0
            if net <= 0:
                continue

            cdt = row.get("created_date_time")
            if cdt:
                from datetime import datetime

                try:
                    if isinstance(cdt, str):
                        dt = datetime.fromisoformat(cdt.replace("Z", "+00:00"))
                    else:
                        dt = cdt
                    hour = dt.hour
                    if 12 <= hour < 17:
                        lunch_total += net
                    else:
                        dinner_total += net
                except:
                    dinner_total += net
            else:
                dinner_total += net

        return [
            {"type": "Lunch", "amount": round(lunch_total, 2)},
            {"type": "Dinner", "amount": round(dinner_total, 2)},
        ]
    else:
        if not location_ids:
            return [
                {"type": "Lunch", "amount": 0.0},
                {"type": "Dinner", "amount": 0.0},
            ]
        with database.db_connection() as conn:
            cur = conn.cursor()
            placeholders = ",".join("?" * len(location_ids))
            cur.execute(
                f"""
                SELECT
                    COALESCE(SUM(lunch_covers), 0) AS sum_lunch,
                    COALESCE(SUM(dinner_covers), 0) AS sum_dinner,
                    COALESCE(SUM(net_total), 0) AS sum_net
                FROM daily_summaries
                WHERE location_id IN ({placeholders})
                  AND date >= ? AND date <= ?
                """,
                (*location_ids, start_date, end_date),
            )
            row = cur.fetchone()
        lunch_c = float(row["sum_lunch"] or 0)
        dinner_c = float(row["sum_dinner"] or 0)
        net = float(row["sum_net"] or 0)
        total_c = lunch_c + dinner_c
        if total_c <= 0:
            split_l, split_d = 0.5 * net, 0.5 * net
        else:
            split_l = net * (lunch_c / total_c)
            split_d = net * (dinner_c / total_c)
        return [
            {"type": "Lunch", "amount": round(split_l, 2)},
            {"type": "Dinner", "amount": round(split_d, 2)},
        ]


def get_daily_service_sales_for_date_range(
    location_ids: List[int],
    start_date: str,
    end_date: str,
) -> List[Dict[str, Any]]:
    """Get daily service period sales."""
    import database

    if database.use_supabase():
        supabase = database.get_supabase_client()
        restaurants = _restaurants_for_location_ids(location_ids)
        result = (
            supabase.table("bill_items")
            .select("bill_date,created_date_time,net_amount,bill_status")
            .in_("restaurant", restaurants)
            .gte("bill_date", start_date)
            .lte("bill_date", end_date)
            .execute()
        )

        daily = {}
        for row in result.data:
            if not _bill_items_success(row.get("bill_status")):
                continue
            net = row.get("net_amount", 0) or 0
            if net <= 0:
                continue

            date = row["bill_date"]
            if date not in daily:
                daily[date] = {"date": date, "Lunch": 0.0, "Dinner": 0.0}

            cdt = row.get("created_date_time")
            if cdt:
                from datetime import datetime

                try:
                    if isinstance(cdt, str):
                        dt = datetime.fromisoformat(cdt.replace("Z", "+00:00"))
                    else:
                        dt = cdt
                    hour = dt.hour
                    if 12 <= hour < 17:
                        daily[date]["Lunch"] += net
                    else:
                        daily[date]["Dinner"] += net
                except:
                    daily[date]["Dinner"] += net
            else:
                daily[date]["Dinner"] += net

        return sorted(daily.values(), key=lambda x: x["date"])
    else:
        if not location_ids:
            return []
        with database.db_connection() as conn:
            cur = conn.cursor()
            placeholders = ",".join("?" * len(location_ids))
            cur.execute(
                f"""
                SELECT date, net_total, lunch_covers, dinner_covers
                FROM daily_summaries
                WHERE location_id IN ({placeholders})
                  AND date >= ? AND date <= ?
                ORDER BY date
                """,
                (*location_ids, start_date, end_date),
            )
            rows = cur.fetchall()
        out = []
        for row in rows:
            d = str(row["date"])
            net = float(row["net_total"] or 0)
            lc = int(row["lunch_covers"] or 0)
            dc = int(row["dinner_covers"] or 0)
            tot = lc + dc
            if tot > 0:
                lunch_amt = net * (lc / tot)
                dinner_amt = net * (dc / tot)
            else:
                lunch_amt = 0.5 * net
                dinner_amt = 0.5 * net
            out.append(
                {
                    "date": d,
                    "Lunch": round(lunch_amt, 2),
                    "Dinner": round(dinner_amt, 2),
                }
            )
        return out


def get_super_category_mtd_totals(
    location_ids: List[int],
    year: int,
    month: int,
) -> Dict[str, float]:
    """Get super category totals for MTD."""
    import database

    start_date = f"{year}-{month:02d}-01"

    if database.use_supabase():
        supabase = database.get_supabase_client()
        result = (
            supabase.table("category_summary")
            .select("category_name,net_amount")
            .in_("location_id", location_ids)
            .gte("date", start_date)
            .execute()
        )

        super_cats = {
            "Food": 0.0,
            "Beverages": 0.0,
            "Other": 0.0,
        }

        for row in result.data:
            cat = (row.get("category_name") or "").lower()
            amount = row.get("net_amount", 0) or 0

            if any(
                kw in cat
                for kw in [
                    "churrasqueira",
                    "tira gosto",
                    "pao de",
                    "sobremesas",
                    "soup",
                    "saladas",
                    "principais",
                    "acompanhamento",
                    "side dish",
                    "food specials",
                    "sandwich",
                    "bowl",
                ]
            ):
                super_cats["Food"] += amount
            elif any(
                kw in cat
                for kw in [
                    "wine",
                    "beer",
                    "cocktail",
                    "soju",
                    "sake",
                    "spirit",
                    "whisky",
                    "rum",
                    "vodka",
                    "gin",
                    "brandy",
                    "mocktail",
                    "beverage",
                    "aerated",
                    "cold",
                    "hot",
                    "kombucha",
                    "mead",
                    "juice",
                    "coffee",
                    "tea",
                ]
            ):
                super_cats["Beverages"] += amount
            else:
                super_cats["Other"] += amount

        return super_cats
    else:
        return {"Food": 0.0, "Beverages": 0.0, "Other": 0.0}


def get_top_items_for_date_range(
    location_ids: List[int],
    start_date: str,
    end_date: str,
    limit: int = 30,
) -> List[Dict[str, Any]]:
    """Get top items by sales for a date range."""
    import database

    if database.use_supabase():
        supabase = database.get_supabase_client()
        restaurants = _restaurants_for_location_ids(location_ids)

        result = (
            supabase.table("bill_items")
            .select("item_name,category_name,net_amount,item_qty,bill_status")
            .in_("restaurant", restaurants)
            .gte("bill_date", start_date)
            .lte("bill_date", end_date)
            .execute()
        )

        item_totals = {}
        for row in result.data:
            if not _bill_items_success(row.get("bill_status")):
                continue
            item = row.get("item_name") or "Unknown"
            if item not in item_totals:
                item_totals[item] = {
                    "item_name": item,
                    "category": row.get("category_name") or "",
                    "amount": 0.0,
                    "qty": 0,
                }
            item_totals[item]["amount"] += row.get("net_amount", 0) or 0
            item_totals[item]["qty"] += row.get("item_qty", 0) or 0

        return sorted(item_totals.values(), key=lambda x: -x["amount"])[:limit]
    else:
        if not location_ids:
            return []
        from database_reads import _CATEGORY_ROW_PREFIX

        with database.db_connection() as conn:
            cur = conn.cursor()
            placeholders = ",".join("?" * len(location_ids))
            cur.execute(
                f"""
                SELECT i.item_name, i.category, SUM(i.qty) AS qty, SUM(i.amount) AS amount
                FROM item_sales i
                INNER JOIN daily_summaries ds ON ds.id = i.summary_id
                WHERE ds.location_id IN ({placeholders})
                  AND ds.date >= ? AND ds.date <= ?
                  AND i.item_name NOT LIKE ?
                GROUP BY i.item_name, i.category
                ORDER BY amount DESC
                LIMIT ?
                """,
                (
                    *location_ids,
                    start_date,
                    end_date,
                    f"{_CATEGORY_ROW_PREFIX}%",
                    limit,
                ),
            )
            rows = cur.fetchall()
        return [
            {
                "item_name": r["item_name"],
                "category": r["category"] or "",
                "qty": int(r["qty"] or 0),
                "amount": float(r["amount"] or 0),
            }
            for r in rows
        ]


def get_payment_breakdown_for_date_range(
    location_ids: List[int],
    start_date: str,
    end_date: str,
) -> Dict[str, float]:
    """Get payment type breakdown from bill_items."""
    import database

    if database.use_supabase():
        supabase = database.get_supabase_client()
        restaurants = _restaurants_for_location_ids(location_ids)

        result = (
            supabase.table("bill_items")
            .select("bill_no,net_amount,payment_type,bill_status")
            .in_("restaurant", restaurants)
            .gte("bill_date", start_date)
            .lte("bill_date", end_date)
            .execute()
        )

        bill_totals = {}
        for row in result.data:
            if not _bill_items_success(row.get("bill_status")):
                continue
            bill_no = row.get("bill_no")
            net = row.get("net_amount", 0) or 0
            if net <= 0:
                continue
            if bill_no not in bill_totals:
                bill_totals[bill_no] = {
                    "payment_type": row.get("payment_type") or "Unknown",
                    "net_amount": net,
                }

        payments = {}
        for bill in bill_totals.values():
            ptype = bill["payment_type"]
            if ptype not in payments:
                payments[ptype] = 0.0
            payments[ptype] += bill["net_amount"]

        return payments
    else:
        if not location_ids:
            return {}
        with database.db_connection() as conn:
            cur = conn.cursor()
            placeholders = ",".join("?" * len(location_ids))
            cur.execute(
                f"""
                SELECT
                    COALESCE(SUM(cash_sales), 0) AS cash_sales,
                    COALESCE(SUM(card_sales), 0) AS card_sales,
                    COALESCE(SUM(gpay_sales), 0) AS gpay_sales,
                    COALESCE(SUM(zomato_sales), 0) AS zomato_sales,
                    COALESCE(SUM(other_sales), 0) AS other_sales
                FROM daily_summaries
                WHERE location_id IN ({placeholders})
                  AND date >= ? AND date <= ?
                """,
                (*location_ids, start_date, end_date),
            )
            row = cur.fetchone()
        if not row:
            return {}
        return {
            "Cash": float(row["cash_sales"] or 0),
            "Card": float(row["card_sales"] or 0),
            "GPay": float(row["gpay_sales"] or 0),
            "Zomato": float(row["zomato_sales"] or 0),
            "Other": float(row["other_sales"] or 0),
        }
