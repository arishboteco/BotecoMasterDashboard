"""Analytics/read query helpers for database module.

This module keeps heavy reporting SQL separate from core write/auth operations.
Uses the new simplified schema.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Set

import streamlit as st

from core.dates import month_bounds
from db.category_rows import CATEGORY_ROW_PREFIX


def _bill_items_success(status: Any) -> bool:
    """Match Petpooja / CSV bill status (case-insensitive)."""
    s = str(status or "").strip().lower()
    return s in ("", "successorder")


def _restaurants_for_location_ids(location_ids: List[int]) -> List[str]:
    """Map outlet ids to Dynamic Report restaurant names on bill_items."""
    from database_writes import LOCATION_ID_TO_RESTAURANT

    return [LOCATION_ID_TO_RESTAURANT.get(int(lid), "Boteco") for lid in location_ids]


def _fetch_daily_summary_rows(
    location_ids: List[int],
    start_date: str,
    end_date: str,
    columns: tuple[str, ...],
) -> List[Dict[str, Any]]:
    """Fetch daily summary rows for SQLite or Supabase with shared filtering."""
    import database
    from services.footfall_override_service import apply_overrides

    if not location_ids:
        return []

    fetch_columns = tuple(dict.fromkeys((*columns, "location_id", "lunch_covers", "dinner_covers")))

    if database.use_supabase():
        supabase = database.get_supabase_client()
        result = (
            supabase.table("daily_summary")
            .select(",".join(fetch_columns))
            .in_("location_id", location_ids)
            .gte("date", start_date)
            .lte("date", end_date)
            .order("date")
            .execute()
        )
        return apply_overrides(
            [dict(row) for row in (result.data or [])],
            location_ids,
            start_date,
            end_date,
        )

    placeholders = ",".join("?" * len(location_ids))
    with database.db_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            f"""
            SELECT {", ".join(fetch_columns)}
            FROM daily_summaries
            WHERE location_id IN ({placeholders})
              AND date >= ? AND date <= ?
            ORDER BY date
            """,
            (*location_ids, start_date, end_date),
        )
        rows = cur.fetchall()
    return apply_overrides([dict(row) for row in rows], location_ids, start_date, end_date)


def _week_key(date_str: str) -> str:
    """Return Monday-based week key, matching existing app output."""
    date = datetime.strptime(date_str, "%Y-%m-%d")
    monday = date - timedelta(days=date.weekday())
    return monday.strftime("%Y-W%W")


def _aggregate_monthly(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Aggregate daily rows to month buckets for footfall trends."""
    monthly: Dict[str, Dict[str, Any]] = {}
    days_per_month: Dict[str, Set[str]] = {}

    for row in rows:
        date_str = str(row.get("date") or "")
        if not date_str:
            continue
        month = date_str[:7]
        if month not in monthly:
            monthly[month] = {
                "month": month,
                "covers": 0,
                "net_total": 0.0,
                "gross_total": 0.0,
            }
            days_per_month[month] = set()

        monthly[month]["covers"] += int(row.get("covers") or 0)
        monthly[month]["net_total"] += float(row.get("net_total") or 0)
        monthly[month]["gross_total"] += float(row.get("gross_total") or 0)
        days_per_month[month].add(date_str)

    out: List[Dict[str, Any]] = []
    for month in sorted(monthly.keys()):
        agg_row = dict(monthly[month])
        agg_row["total_days"] = len(days_per_month.get(month, set()))
        out.append(agg_row)
    return out


def _aggregate_weekly(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Aggregate daily rows to ISO-like Monday week keys for trends."""
    weekly: Dict[str, Dict[str, Any]] = {}
    days_per_week: Dict[str, Set[str]] = {}

    for row in rows:
        date_str = str(row.get("date") or "")
        if not date_str:
            continue
        week = _week_key(date_str)
        if week not in weekly:
            weekly[week] = {
                "week": week,
                "covers": 0,
                "net_total": 0.0,
            }
            days_per_week[week] = set()

        weekly[week]["covers"] += int(row.get("covers") or 0)
        weekly[week]["net_total"] += float(row.get("net_total") or 0)
        days_per_week[week].add(date_str)

    out: List[Dict[str, Any]] = []
    for week in sorted(weekly.keys()):
        agg_row = dict(weekly[week])
        agg_row["total_days"] = len(days_per_week.get(week, set()))
        out.append(agg_row)
    return out


def _sum_payment_buckets(rows: List[Dict[str, Any]]) -> Dict[str, float]:
    """Sum payment columns into standard app payment buckets."""
    totals = {
        "Cash": 0.0,
        "Card": 0.0,
        "GPay": 0.0,
        "Zomato": 0.0,
        "Other": 0.0,
    }
    for row in rows:
        totals["Cash"] += float(row.get("cash_sales") or 0)
        totals["Card"] += float(row.get("card_sales") or 0)
        totals["GPay"] += float(row.get("gpay_sales") or 0)
        totals["Zomato"] += float(row.get("zomato_sales") or 0)
        totals["Other"] += float(row.get("other_sales") or 0)
    return totals


@st.cache_data(ttl=600)
def get_monthly_footfall_multi(
    location_ids: List[int], start_date: str, end_date: str
) -> List[Dict[str, Any]]:
    """Aggregate covers by month across locations for a date range."""
    rows = _fetch_daily_summary_rows(
        location_ids,
        start_date,
        end_date,
        ("date", "covers", "net_total", "gross_total"),
    )
    return _aggregate_monthly(rows)


@st.cache_data(ttl=600)
def get_weekly_footfall_multi(
    location_ids: List[int], start_date: str, end_date: str
) -> List[Dict[str, Any]]:
    """Aggregate covers by ISO week across locations for a date range."""
    rows = _fetch_daily_summary_rows(
        location_ids,
        start_date,
        end_date,
        ("date", "covers", "net_total"),
    )
    return _aggregate_weekly(rows)


@st.cache_data(ttl=600)
def get_daily_sales_for_date_range(
    location_ids: List[int], start_date: str, end_date: str
) -> List[Dict[str, Any]]:
    """Get daily sales data for a date range."""
    return _fetch_daily_summary_rows(
        location_ids,
        start_date,
        end_date,
        (
            "date",
            "location_id",
            "net_total",
            "gross_total",
            "covers",
            "discount",
            "lunch_covers",
            "dinner_covers",
        ),
    )


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

        rows = get_category_totals_for_date_range(location_ids, start_date, end_date)
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
                except (ValueError, TypeError, AttributeError):
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
                except (ValueError, TypeError, AttributeError):
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

    start_date, _ = month_bounds(year, month)

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
                    f"{CATEGORY_ROW_PREFIX}%",
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


def _normalize_provider(raw: str) -> str:
    """Map a raw Payment Type cell to a human-readable provider label.

    More granular than the bucket classifier: GPay, UPI, Paytm, PhonePe,
    Wallet, Bharat QR, Zomato, Swiggy, Cash, Card, Online, Part Payment.
    Unrecognised values return "Other".
    """
    s = str(raw or "").strip().lower()
    if not s or s in ("nan", "none", "null", "-"):
        return "Other"
    if "zomato" in s:
        return "Zomato"
    if "swiggy" in s:
        return "Swiggy"
    if "paytm" in s:
        return "Paytm"
    if "phonepe" in s or "phone pe" in s:
        return "PhonePe"
    if "gpay" in s or "g pay" in s or ("google" in s and "pay" in s):
        return "GPay"
    if "bharat qr" in s:
        return "Bharat QR"
    if s == "qr":
        return "Bharat QR"
    if s == "upi" or "upi" in s:
        return "UPI"
    if "online" in s:
        return "Online"
    if "wallet" in s:
        return "Wallet"
    if s == "cash":
        return "Cash"
    if (
        "card" in s
        or "credit" in s
        or "debit" in s
        or "amex" in s
        or "visa" in s
        or "master" in s
        or "pos" in s
    ):
        return "Card"
    if "part payment" in s:
        return "Part Payment"
    return "Other"


@st.cache_data(ttl=300)
def get_payment_provider_breakdown(
    location_ids: List[int],
    start_date: str,
    end_date: str,
) -> List[Dict[str, Any]]:
    """Aggregate gross_amount and txn count by payment provider across a date range.

    Supabase: reads bill_items.payment_type per bill (summary rows only — rows
    with gross_amount > 0) and groups by normalized provider label.
    SQLite: falls back to daily_summaries payment columns (5-bucket precision).

    Returns list of {provider, txn_count, gross_amount} sorted by gross_amount desc.
    """
    import database

    if database.use_supabase():
        supabase = database.get_supabase_client()
        restaurants = _restaurants_for_location_ids(location_ids)
        result = (
            supabase.table("bill_items")
            .select("payment_type,gross_amount,bill_no,bill_status")
            .in_("restaurant", restaurants)
            .gte("bill_date", start_date)
            .lte("bill_date", end_date)
            .execute()
        )

        # Aggregate at bill level (one row per bill_no that has gross_amount > 0)
        seen_bills: set = set()
        totals: Dict[str, Dict[str, Any]] = {}
        for row in result.data:
            if not _bill_items_success(row.get("bill_status")):
                continue
            gross = float(row.get("gross_amount") or 0)
            if gross <= 0:
                continue
            bill_no = row.get("bill_no", "")
            if bill_no in seen_bills:
                continue
            seen_bills.add(bill_no)

            provider = _normalize_provider(row.get("payment_type", ""))
            if provider not in totals:
                totals[provider] = {"provider": provider, "txn_count": 0, "gross_amount": 0.0}
            totals[provider]["txn_count"] += 1
            totals[provider]["gross_amount"] += gross

        return sorted(totals.values(), key=lambda x: -x["gross_amount"])

    else:
        if not location_ids:
            return []
        with database.db_connection() as conn:
            cur = conn.cursor()
            placeholders = ",".join("?" * len(location_ids))
            cur.execute(
                f"""
                SELECT
                    COALESCE(SUM(cash_sales), 0)   AS cash,
                    COALESCE(SUM(card_sales), 0)   AS card,
                    COALESCE(SUM(gpay_sales), 0)   AS gpay,
                    COALESCE(SUM(zomato_sales), 0) AS zomato,
                    COALESCE(SUM(other_sales), 0)  AS other,
                    COUNT(*) AS days
                FROM daily_summaries
                WHERE location_id IN ({placeholders})
                  AND date >= ? AND date <= ?
                """,
                (*location_ids, start_date, end_date),
            )
            row = cur.fetchone()
        if not row:
            return []
        buckets = [
            ("Cash", float(row["cash"] or 0)),
            ("Card", float(row["card"] or 0)),
            ("GPay / UPI", float(row["gpay"] or 0)),
            ("Zomato / Swiggy", float(row["zomato"] or 0)),
            ("Others", float(row["other"] or 0)),
        ]
        return [
            {"provider": lbl, "txn_count": None, "gross_amount": amt}
            for lbl, amt in buckets
            if amt > 0
        ]


def get_payment_breakdown_for_date_range(
    location_ids: List[int],
    start_date: str,
    end_date: str,
) -> Dict[str, float]:
    """Get payment type breakdown for a date range.

    Reads pre-aggregated payment columns from daily_summary (populated during
    upload from the correctly-parsed Dynamic Report data).
    """
    rows = _fetch_daily_summary_rows(
        location_ids,
        start_date,
        end_date,
        ("cash_sales", "card_sales", "gpay_sales", "zomato_sales", "other_sales"),
    )
    if not rows:
        return {}
    return _sum_payment_buckets(rows)
