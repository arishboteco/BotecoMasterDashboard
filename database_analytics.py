"""Analytics/read query helpers for database module.

This module keeps heavy reporting SQL separate from core write/auth operations.
Uses the new simplified schema.
"""

from __future__ import annotations

from typing import Any, Dict, List
import streamlit as st


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
        for row in result.data:
            month = row["date"][:7]
            if month not in monthly:
                monthly[month] = {
                    "month": month,
                    "covers": 0,
                    "net_total": 0.0,
                    "gross_total": 0.0,
                }
            monthly[month]["covers"] += row.get("covers", 0) or 0
            monthly[month]["net_total"] += row.get("net_total", 0) or 0
            monthly[month]["gross_total"] += row.get("gross_total", 0) or 0

        return sorted(monthly.values(), key=lambda x: x["month"])
    else:
        return []


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
        for row in result.data:
            from datetime import datetime, timedelta

            date = datetime.strptime(row["date"], "%Y-%m-%d")
            monday = date - timedelta(days=date.weekday())
            week_key = monday.strftime("%Y-W%W")
            if week_key not in weekly:
                weekly[week_key] = {"week": week_key, "covers": 0, "net_total": 0.0}
            weekly[week_key]["covers"] += row.get("covers", 0) or 0
            weekly[week_key]["net_total"] += row.get("net_total", 0) or 0

        return sorted(weekly.values(), key=lambda x: x["week"])
    else:
        return []


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
        return []


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
        return []


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
        result = (
            supabase.table("bill_items")
            .select("created_date_time,net_amount,bill_status")
            .in_("restaurant", ["Boteco", "Boteco - Bagmane"])
            .gte("bill_date", start_date)
            .lte("bill_date", end_date)
            .execute()
        )

        lunch_total = 0.0
        dinner_total = 0.0

        for row in result.data:
            if row.get("bill_status") != "SuccessOrder":
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
        return []


def get_daily_service_sales_for_date_range(
    location_ids: List[int],
    start_date: str,
    end_date: str,
) -> List[Dict[str, Any]]:
    """Get daily service period sales."""
    import database

    if database.use_supabase():
        supabase = database.get_supabase_client()
        result = (
            supabase.table("bill_items")
            .select("bill_date,created_date_time,net_amount,bill_status")
            .in_("restaurant", ["Boteco", "Boteco - Bagmane"])
            .gte("bill_date", start_date)
            .lte("bill_date", end_date)
            .execute()
        )

        daily = {}
        for row in result.data:
            if row.get("bill_status") != "SuccessOrder":
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
        return []


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

        location_restaurants = {
            1: "Boteco",
            2: "Boteco - Bagmane",
        }
        restaurants = [location_restaurants.get(lid, "Boteco") for lid in location_ids]

        result = (
            supabase.table("bill_items")
            .select("item_name,category_name,net_amount,item_qty")
            .in_("restaurant", restaurants)
            .gte("bill_date", start_date)
            .lte("bill_date", end_date)
            .eq("bill_status", "SuccessOrder")
            .execute()
        )

        item_totals = {}
        for row in result.data:
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
        return []


def get_payment_breakdown_for_date_range(
    location_ids: List[int],
    start_date: str,
    end_date: str,
) -> Dict[str, float]:
    """Get payment type breakdown from bill_items."""
    import database

    if database.use_supabase():
        supabase = database.get_supabase_client()

        result = (
            supabase.table("bill_items")
            .select("bill_no,net_amount,payment_type,bill_status")
            .in_("restaurant", ["Boteco", "Boteco - Bagmane"])
            .gte("bill_date", start_date)
            .lte("bill_date", end_date)
            .eq("bill_status", "SuccessOrder")
            .execute()
        )

        bill_totals = {}
        for row in result.data:
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
        return {}
