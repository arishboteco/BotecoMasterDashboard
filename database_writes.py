"""Write/update/delete operations for the new simplified database schema."""

from __future__ import annotations

from typing import Dict, List, Any, Tuple
import database


# Restaurant to location_id mapping
RESTAURANT_MAP = {
    "Boteco": 1,
    "Boteco - Bagmane": 2,
}


def _get_location_id(restaurant: str) -> int:
    """Map restaurant name to location_id."""
    return RESTAURANT_MAP.get(restaurant, 1)


def ensure_default_locations() -> None:
    """Ensure Boteco - Indiqube and Boteco - Bagmane exist in Supabase."""
    from database import get_supabase_client

    client = get_supabase_client()
    existing = client.table("locations").select("id").execute()

    existing_names = {row["name"] for row in existing.data} if existing.data else set()

    defaults = [
        {
            "id": 1,
            "name": "Boteco - Indiqube",
            "target_monthly_sales": 5000000.0,
            "target_daily_sales": 166666.66666666666,
        },
        {
            "id": 2,
            "name": "Boteco - Bagmane",
            "target_monthly_sales": 5000000.0,
            "target_daily_sales": 166666.66666666666,
        },
    ]

    for loc in defaults:
        if loc["name"] not in existing_names:
            client.table("locations").upsert(loc, on_conflict="id").execute()


def save_bill_items(supabase, records: List[Dict]) -> None:
    """Bulk insert bill_items records."""
    if not records:
        return
    supabase.table("bill_items").insert(records).execute()


def save_daily_summary(supabase, location_id: int, date: str, data: Dict) -> int:
    """Save or update daily summary."""
    row_data = {
        "location_id": location_id,
        "date": date,
        "gross_total": data.get("gross_total", 0),
        "net_total": data.get("net_total", 0),
        "covers": data.get("covers", 0),
        "discount": data.get("discount", 0),
        "cgst": data.get("cgst", 0),
        "sgst": data.get("sgst", 0),
        "service_charge": data.get("service_charge", 0),
        "gst_on_service_charge": data.get("gst_on_service_charge", 0),
        "cancelled_amount": data.get("cancelled_amount", 0),
        "complementary_amount": data.get("complementary_amount", 0),
    }

    result = (
        supabase.table("daily_summary")
        .upsert(row_data, on_conflict="location_id,date")
        .execute()
    )
    return result.data[0]["id"]


def save_category_summary(
    supabase,
    location_id: int,
    date: str,
    category_name: str,
    net_amount: float,
    qty: int,
) -> None:
    """Save or update category summary."""
    row_data = {
        "location_id": location_id,
        "date": date,
        "category_name": category_name,
        "net_amount": round(net_amount, 2),
        "qty": qty,
    }

    supabase.table("category_summary").upsert(
        row_data, on_conflict="location_id,date,category_name"
    ).execute()


def save_category_summary_batch(supabase, records: List[Dict]) -> None:
    """Bulk insert category_summary records."""
    if not records:
        return

    formatted_records = [
        {
            "location_id": r["location_id"],
            "date": r["date"],
            "category_name": r["category_name"],
            "net_amount": round(r["net_amount"], 2),
            "qty": r["qty"],
        }
        for r in records
    ]

    for record in formatted_records:
        supabase.table("category_summary").upsert(
            record, on_conflict="location_id,date,category_name"
        ).execute()


def delete_bill_items_by_date(supabase, date: str, location_id: int) -> None:
    """Delete bill_items for a specific date and location."""
    supabase.table("bill_items").delete().eq("bill_date", date).eq(
        "restaurant", "Boteco" if location_id == 1 else "Boteco - Bagmane"
    ).execute()


def delete_daily_summary(supabase, date: str, location_id: int) -> None:
    """Delete daily_summary for a specific date and location."""
    supabase.table("daily_summary").delete().eq("date", date).eq(
        "location_id", location_id
    ).execute()


def delete_category_summary(supabase, date: str, location_id: int) -> None:
    """Delete category_summary for a specific date and location."""
    supabase.table("category_summary").delete().eq("date", date).eq(
        "location_id", location_id
    ).execute()


def clear_all_data(supabase) -> None:
    """Clear all data from bill_items, daily_summary, and category_summary."""
    supabase.table("category_summary").delete().neq("id", 0).execute()
    supabase.table("daily_summary").delete().neq("id", 0).execute()
    supabase.table("bill_items").delete().neq("id", 0).execute()


def wipe_all_data() -> tuple:
    """Delete ALL operational data. Returns (counts, errors)."""
    from typing import Dict, List
    from database import use_supabase, get_supabase_client, get_supabase_admin_client

    counts = {}
    errors = []

    if not use_supabase():
        errors.append("Supabase not configured")
        return counts, errors

    try:
        admin = get_supabase_admin_client()
        if admin is None:
            admin = get_supabase_client()

        if admin is None:
            errors.append("Could not get Supabase client")
            return counts, errors

        # Count before delete
        for table in ["bill_items", "daily_summary", "category_summary"]:
            result = admin.table(table).select("id", count="exact").execute()
            counts[table] = result.count

        # Delete
        clear_all_data(admin)

    except Exception as e:
        errors.append(str(e))

    return counts, errors
