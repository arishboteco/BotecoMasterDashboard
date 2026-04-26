"""Write/update/delete operations for SQLite and Supabase backends."""

from __future__ import annotations

import calendar
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import database
from boteco_logger import get_logger
from db.category_rows import CATEGORY_ROW_PREFIX
from db.table_names import (
    SQLITE_DAILY_SUMMARIES,
    SQLITE_ITEM_SALES,
    SQLITE_SERVICE_SALES,
    SUPABASE_BILL_ITEMS,
    SUPABASE_CATEGORY_SUMMARY,
    SUPABASE_DAILY_SUMMARY,
)

logger = get_logger(__name__)

# Restaurant CSV column value → location_id (Supabase / app convention)
RESTAURANT_MAP = {
    "Boteco": 1,
    "Boteco - Indiqube": 1,
    "Boteco - Bagmane": 2,
}

LOCATION_ID_TO_RESTAURANT = {
    1: "Boteco",
    2: "Boteco - Bagmane",
}

# PostgREST performs best with modest payload sizes; large CSVs are split across requests.
_SUPABASE_ROW_CHUNK = 500


def _get_location_id(restaurant: str) -> int:
    """Map restaurant name from Dynamic Report CSV to location_id."""
    return RESTAURANT_MAP.get(restaurant, 1)


def ensure_default_locations() -> None:
    """Ensure default outlets exist (Supabase upsert; SQLite seed if DB is empty)."""
    if database.use_supabase():
        from database import get_supabase_client

        client = get_supabase_client()
        if client is None:
            return
        existing = client.table("locations").select("id,name").execute()
        existing_names = {row["name"] for row in (existing.data or [])}
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
        return

    with database.db_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) AS c FROM locations")
        if int(cur.fetchone()["c"]) > 0:
            return
        cur.executemany(
            """
            INSERT INTO locations (id, name, target_monthly_sales, target_daily_sales)
            VALUES (?, ?, ?, ?)
            """,
            [
                (1, "Boteco - Indiqube", 5000000.0, 166666.66666666666),
                (2, "Boteco - Bagmane", 5000000.0, 166666.66666666666),
            ],
        )
        conn.commit()


def backfill_weekday_weighted_targets() -> Tuple[int, int]:
    """One-time backfill for weekday-weighted targets. No-op when using Supabase."""
    if database.use_supabase():
        return 0, 0
    # Legacy SQLite path could live here; currently unused for cloud-first workflow.
    return 0, 0


def upsert_daily_summary_supabase(
    supabase: Any, location_id: int, date: str, data: Dict[str, Any]
) -> int:
    """Upsert one row in public.daily_summary (Supabase simplified schema)."""
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
        "cash_sales": data.get("cash_sales", 0),
        "card_sales": data.get("card_sales", 0),
        "gpay_sales": data.get("gpay_sales", 0),
        "zomato_sales": data.get("zomato_sales", 0),
        "other_sales": data.get("other_sales", 0),
        "order_count": data.get("order_count", 0),
    }
    result = (
        supabase.table(SUPABASE_DAILY_SUMMARY)
        .upsert(row_data, on_conflict="location_id,date")
        .execute()
    )
    return int(result.data[0]["id"])


def upsert_daily_summaries_supabase_batch(supabase: Any, rows: List[Dict[str, Any]]) -> None:
    """Bulk upsert daily_summary rows (one HTTP round-trip per chunk)."""
    if not rows:
        return
    for i in range(0, len(rows), _SUPABASE_ROW_CHUNK):
        chunk = rows[i : i + _SUPABASE_ROW_CHUNK]
        supabase.table(SUPABASE_DAILY_SUMMARY).upsert(
            chunk, on_conflict="location_id,date"
        ).execute()


def save_daily_summary(location_id: int, data: Dict[str, Any]) -> int:
    """Save or update daily summary (public API for database.save_daily_summary)."""
    date_str = str(data.get("date", "")).strip()
    if not date_str:
        raise ValueError("save_daily_summary requires data['date']")

    if database.use_supabase():
        client = database.get_supabase_client()
        if client is None:
            raise RuntimeError("Supabase client not available")
        return upsert_daily_summary_supabase(client, location_id, date_str, data)

    return _save_daily_summary_sqlite(location_id, date_str, data)


def _save_daily_summary_sqlite(location_id: int, date_str: str, data: Dict[str, Any]) -> int:
    """Persist legacy daily_summaries + item_sales + service_sales."""
    with database.db_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            f"""
            SELECT id FROM {SQLITE_DAILY_SUMMARIES}
            WHERE location_id = ? AND date = ?
            """,
            (location_id, date_str),
        )
        row = cur.fetchone()
        if row:
            summary_id = int(row["id"])
            cur.execute(
                f"""
                UPDATE {SQLITE_DAILY_SUMMARIES} SET
                    covers = ?, turns = ?, gross_total = ?, net_total = ?,
                    cash_sales = ?, card_sales = ?, gpay_sales = ?, zomato_sales = ?,
                    other_sales = ?, service_charge = ?, cgst = ?, sgst = ?,
                    discount = ?, complimentary = ?, apc = ?, target = ?, pct_target = ?,
                    mtd_total_covers = ?, mtd_net_sales = ?, mtd_discount = ?,
                    mtd_avg_daily = ?, mtd_target = ?, mtd_pct_target = ?
                WHERE id = ?
                """,
                (
                    int(data.get("covers", 0) or 0),
                    float(data.get("turns", 0) or 0),
                    float(data.get("gross_total", 0) or 0),
                    float(data.get("net_total", 0) or 0),
                    float(data.get("cash_sales", 0) or 0),
                    float(data.get("card_sales", 0) or 0),
                    float(data.get("gpay_sales", 0) or 0),
                    float(data.get("zomato_sales", 0) or 0),
                    float(data.get("other_sales", 0) or 0),
                    float(data.get("service_charge", 0) or 0),
                    float(data.get("cgst", 0) or 0),
                    float(data.get("sgst", 0) or 0),
                    float(data.get("discount", 0) or 0),
                    float(data.get("complimentary", 0) or 0),
                    float(data.get("apc", 0) or 0),
                    float(data.get("target", 166667) or 166667),
                    float(data.get("pct_target", 0) or 0),
                    int(data.get("mtd_total_covers", 0) or 0),
                    float(data.get("mtd_net_sales", 0) or 0),
                    float(data.get("mtd_discount", 0) or 0),
                    float(data.get("mtd_avg_daily", 0) or 0),
                    float(data.get("mtd_target", 5000000) or 5000000),
                    float(data.get("mtd_pct_target", 0) or 0),
                    summary_id,
                ),
            )
        else:
            cur.execute(
                f"""
                INSERT INTO {SQLITE_DAILY_SUMMARIES} (
                    location_id, date, covers, turns, gross_total, net_total,
                    cash_sales, card_sales, gpay_sales, zomato_sales, other_sales,
                    service_charge, cgst, sgst, discount, complimentary, apc,
                    target, pct_target, mtd_total_covers, mtd_net_sales, mtd_discount,
                    mtd_avg_daily, mtd_target, mtd_pct_target
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    location_id,
                    date_str,
                    int(data.get("covers", 0) or 0),
                    float(data.get("turns", 0) or 0),
                    float(data.get("gross_total", 0) or 0),
                    float(data.get("net_total", 0) or 0),
                    float(data.get("cash_sales", 0) or 0),
                    float(data.get("card_sales", 0) or 0),
                    float(data.get("gpay_sales", 0) or 0),
                    float(data.get("zomato_sales", 0) or 0),
                    float(data.get("other_sales", 0) or 0),
                    float(data.get("service_charge", 0) or 0),
                    float(data.get("cgst", 0) or 0),
                    float(data.get("sgst", 0) or 0),
                    float(data.get("discount", 0) or 0),
                    float(data.get("complimentary", 0) or 0),
                    float(data.get("apc", 0) or 0),
                    float(data.get("target", 166667) or 166667),
                    float(data.get("pct_target", 0) or 0),
                    int(data.get("mtd_total_covers", 0) or 0),
                    float(data.get("mtd_net_sales", 0) or 0),
                    float(data.get("mtd_discount", 0) or 0),
                    float(data.get("mtd_avg_daily", 0) or 0),
                    float(data.get("mtd_target", 5000000) or 5000000),
                    float(data.get("mtd_pct_target", 0) or 0),
                ),
            )
            summary_id = int(cur.lastrowid)

        cur.execute(f"DELETE FROM {SQLITE_ITEM_SALES} WHERE summary_id = ?", (summary_id,))
        cur.execute(f"DELETE FROM {SQLITE_SERVICE_SALES} WHERE summary_id = ?", (summary_id,))

        for cat in data.get("categories") or []:
            name = str(cat.get("category", "") or "").strip()
            if not name:
                continue
            cur.execute(
                f"""
                INSERT INTO {SQLITE_ITEM_SALES} (summary_id, item_name, category, qty, amount)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    summary_id,
                    f"{CATEGORY_ROW_PREFIX}{name}",
                    name,
                    int(cat.get("qty", 0) or 0),
                    float(cat.get("amount", 0) or 0),
                ),
            )

        for item in data.get("top_items") or []:
            iname = str(item.get("item_name", "") or "").strip()
            if not iname:
                continue
            cur.execute(
                f"""
                INSERT INTO {SQLITE_ITEM_SALES} (summary_id, item_name, category, qty, amount)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    summary_id,
                    iname,
                    str(item.get("category", "") or ""),
                    int(item.get("qty", 0) or 0),
                    float(item.get("amount", 0) or 0),
                ),
            )

        for svc in data.get("services") or []:
            stype = str(svc.get("type", "") or "").strip()
            if not stype:
                continue
            cur.execute(
                f"""
                INSERT INTO {SQLITE_SERVICE_SALES} (summary_id, service_type, amount)
                VALUES (?, ?, ?)
                """,
                (summary_id, stype, float(svc.get("amount", 0) or 0)),
            )

        conn.commit()
    return summary_id


def save_bill_items(supabase: Any, records: List[Dict[str, Any]]) -> None:
    """Bulk insert bill_items records (Supabase only), chunked to avoid timeouts."""
    if not records:
        return
    for i in range(0, len(records), _SUPABASE_ROW_CHUNK):
        supabase.table(SUPABASE_BILL_ITEMS).insert(records[i : i + _SUPABASE_ROW_CHUNK]).execute()


def save_category_summary(
    supabase: Any,
    location_id: int,
    date: str,
    category_name: str,
    net_amount: float,
    qty: int,
) -> None:
    """Save or update one category_summary row (Supabase)."""
    row_data = {
        "location_id": location_id,
        "date": date,
        "category_name": category_name,
        "net_amount": round(net_amount, 2),
        "qty": qty,
    }
    supabase.table(SUPABASE_CATEGORY_SUMMARY).upsert(
        row_data, on_conflict="location_id,date,category_name"
    ).execute()


def save_category_summary_batch(supabase: Any, records: List[Dict[str, Any]]) -> None:
    """Bulk upsert category_summary records (Supabase), chunked."""
    if not records:
        return
    normalized = [
        {
            "location_id": r["location_id"],
            "date": r["date"],
            "category_name": r["category_name"],
            "net_amount": round(float(r["net_amount"]), 2),
            "qty": int(r["qty"]),
        }
        for r in records
    ]
    for i in range(0, len(normalized), _SUPABASE_ROW_CHUNK):
        chunk = normalized[i : i + _SUPABASE_ROW_CHUNK]
        supabase.table(SUPABASE_CATEGORY_SUMMARY).upsert(
            chunk, on_conflict="location_id,date,category_name"
        ).execute()


def delete_bill_items_by_date(supabase: Any, date: str, location_id: int) -> None:
    """Delete bill_items for a specific date and location (Supabase)."""
    restaurant = LOCATION_ID_TO_RESTAURANT.get(location_id, "Boteco")
    supabase.table(SUPABASE_BILL_ITEMS).delete().eq("bill_date", date).eq(
        "restaurant", restaurant
    ).execute()


def delete_daily_summary(supabase: Any, date: str, location_id: int) -> None:
    """Delete daily_summary row (Supabase)."""
    supabase.table(SUPABASE_DAILY_SUMMARY).delete().eq("date", date).eq(
        "location_id", location_id
    ).execute()


def delete_category_summary(supabase: Any, date: str, location_id: int) -> None:
    """Delete category_summary rows (Supabase)."""
    supabase.table(SUPABASE_CATEGORY_SUMMARY).delete().eq("date", date).eq(
        "location_id", location_id
    ).execute()


def delete_bill_items_by_dates_locs(supabase: Any, dates_locs: set) -> None:
    """Delete bill_items for multiple (date, location_id) pairs in few queries.

    Groups by restaurant to minimise round-trips (one query per restaurant).
    """
    by_restaurant: Dict[str, List[str]] = {}
    for date_str, loc_id in dates_locs:
        restaurant = LOCATION_ID_TO_RESTAURANT.get(loc_id, "Boteco")
        by_restaurant.setdefault(restaurant, []).append(date_str)
    for restaurant, date_list in by_restaurant.items():
        supabase.table(SUPABASE_BILL_ITEMS).delete().in_("bill_date", date_list).eq(
            "restaurant", restaurant
        ).execute()


def delete_category_summary_batch(supabase: Any, dates_locs: set) -> None:
    """Delete category_summary for multiple (date, location_id) pairs in few queries.

    Groups by location_id to minimise round-trips (one query per location).
    """
    by_loc: Dict[int, List[str]] = {}
    for date_str, loc_id in dates_locs:
        by_loc.setdefault(loc_id, []).append(date_str)
    for loc_id, date_list in by_loc.items():
        supabase.table(SUPABASE_CATEGORY_SUMMARY).delete().in_("date", date_list).eq(
            "location_id", loc_id
        ).execute()


def clear_all_data(supabase: Any) -> None:
    """Clear operational tables (Supabase)."""
    supabase.table(SUPABASE_CATEGORY_SUMMARY).delete().neq("id", 0).execute()
    supabase.table(SUPABASE_DAILY_SUMMARY).delete().neq("id", 0).execute()
    supabase.table(SUPABASE_BILL_ITEMS).delete().neq("id", 0).execute()


def wipe_all_data() -> Tuple[Dict[str, int], List[str]]:
    """Delete ALL operational data. Preserves locations, users."""
    counts: Dict[str, int] = {}
    errors: List[str] = []

    if database.use_supabase():
        try:
            admin = database.get_supabase_admin_client()
            if admin is None:
                admin = database.get_supabase_client()
            if admin is None:
                errors.append("Could not get Supabase client")
                return counts, errors
            for table in [
                SUPABASE_BILL_ITEMS,
                SUPABASE_DAILY_SUMMARY,
                SUPABASE_CATEGORY_SUMMARY,
            ]:
                result = admin.table(table).select("id", count="exact").execute()
                counts[table] = int(result.count or 0)
            clear_all_data(admin)
        except Exception as e:
            errors.append(str(e))
        return counts, errors

    try:
        with database.db_connection() as conn:
            cur = conn.cursor()
            cur.execute(f"SELECT COUNT(*) FROM {SQLITE_ITEM_SALES}")
            counts["item_sales"] = int(cur.fetchone()[0])
            cur.execute(f"SELECT COUNT(*) FROM {SQLITE_SERVICE_SALES}")
            counts["service_sales"] = int(cur.fetchone()[0])
            cur.execute("SELECT COUNT(*) FROM upload_history")
            counts["upload_history"] = int(cur.fetchone()[0])
            cur.execute(f"SELECT COUNT(*) FROM {SQLITE_DAILY_SUMMARIES}")
            counts["daily_summaries"] = int(cur.fetchone()[0])
            cur.execute(f"DELETE FROM {SQLITE_ITEM_SALES}")
            cur.execute(f"DELETE FROM {SQLITE_SERVICE_SALES}")
            cur.execute("DELETE FROM upload_history")
            cur.execute(f"DELETE FROM {SQLITE_DAILY_SUMMARIES}")
            conn.commit()
    except Exception as e:
        errors.append(str(e))
    return counts, errors


def save_upload_record(
    location_id: int,
    date: str,
    filename: str,
    file_type: str,
    uploaded_by: str,
) -> None:
    """Record a successful upload for audit/history."""
    if database.use_supabase():
        client = database.get_supabase_client()
        if client is None:
            raise RuntimeError("Supabase client not available")
        client.table("upload_history").insert(
            {
                "location_id": location_id,
                "date": date,
                "filename": filename,
                "file_type": file_type,
                "uploaded_by": uploaded_by,
            }
        ).execute()
        return

    with database.db_connection() as conn:
        conn.execute(
            """
            INSERT INTO upload_history (location_id, date, filename, file_type, uploaded_by)
            VALUES (?, ?, ?, ?, ?)
            """,
            (location_id, date, filename, file_type, uploaded_by),
        )
        conn.commit()


def save_upload_records_batch(rows: List[Dict[str, Any]]) -> None:
    """Insert multiple upload_history rows in few round-trips."""
    if not rows:
        return
    if database.use_supabase():
        client = database.get_supabase_client()
        if client is None:
            raise RuntimeError("Supabase client not available")
        for i in range(0, len(rows), _SUPABASE_ROW_CHUNK):
            client.table("upload_history").insert(rows[i : i + _SUPABASE_ROW_CHUNK]).execute()
        return

    with database.db_connection() as conn:
        conn.executemany(
            """
            INSERT INTO upload_history (location_id, date, filename, file_type, uploaded_by)
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                (
                    int(r["location_id"]),
                    r["date"],
                    r["filename"],
                    r["file_type"],
                    r["uploaded_by"],
                )
                for r in rows
            ],
        )
        conn.commit()


def delete_daily_summary_for_location_date(location_id: int, date: str) -> bool:
    """Remove one day's summary and child rows. Leaves upload_history."""
    if database.use_supabase():
        client = database.get_supabase_client()
        if client is None:
            return False
        delete_bill_items_by_date(client, date, location_id)
        delete_category_summary(client, date, location_id)
        delete_daily_summary(client, date, location_id)
        return True

    with database.db_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            f"SELECT id FROM {SQLITE_DAILY_SUMMARIES} WHERE location_id = ? AND date = ?",
            (location_id, date),
        )
        row = cur.fetchone()
        if not row:
            return False
        sid = int(row["id"])
        cur.execute(f"DELETE FROM {SQLITE_ITEM_SALES} WHERE summary_id = ?", (sid,))
        cur.execute(f"DELETE FROM {SQLITE_SERVICE_SALES} WHERE summary_id = ?", (sid,))
        cur.execute(f"DELETE FROM {SQLITE_DAILY_SUMMARIES} WHERE id = ?", (sid,))
        conn.commit()
    return True


def update_daily_summary_covers_only(
    location_id: int,
    date: str,
    covers: int,
    lunch_covers: Optional[int] = None,
    dinner_covers: Optional[int] = None,
) -> bool:
    """Update covers fields on an existing daily row."""
    if database.use_supabase():
        client = database.get_supabase_client()
        if client is None:
            return False
        client.table(SUPABASE_DAILY_SUMMARY).update({"covers": covers}).eq(
            "location_id", location_id
        ).eq("date", date).execute()
        return True

    sets = ["covers = ?"]
    params: List[Any] = [covers]
    if lunch_covers is not None:
        sets.append("lunch_covers = ?")
        params.append(lunch_covers)
    if dinner_covers is not None:
        sets.append("dinner_covers = ?")
        params.append(dinner_covers)
    params.extend([location_id, date])
    with database.db_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            f"UPDATE {SQLITE_DAILY_SUMMARIES} SET {', '.join(sets)} "
            "WHERE location_id = ? AND date = ?",
            tuple(params),
        )
        conn.commit()
        return cur.rowcount > 0


def create_location(
    name: str,
    monthly_target: float = 5_000_000,
    seat_count: Optional[int] = None,
) -> Tuple[bool, str]:
    """Add a new outlet."""
    name = (name or "").strip()
    if not name:
        return False, "Name is required"
    _now = datetime.now()
    _days = calendar.monthrange(_now.year, _now.month)[1]
    daily = float(monthly_target) / _days if monthly_target else float(5_000_000) / _days

    if database.use_supabase():
        client = database.get_supabase_client()
        if client is None:
            return False, "Database unavailable"
        try:
            row: Dict[str, Any] = {
                "name": name,
                "target_monthly_sales": float(monthly_target),
                "target_daily_sales": daily,
            }
            if seat_count is not None:
                row["seat_count"] = seat_count
            client.table("locations").insert(row).execute()
        except Exception as e:
            return False, str(e)
        return True, ""

    with database.db_connection() as conn:
        cur = conn.cursor()
        try:
            cur.execute(
                """
                INSERT INTO locations (name, target_monthly_sales, target_daily_sales, seat_count)
                VALUES (?, ?, ?, ?)
                """,
                (name, float(monthly_target), daily, seat_count),
            )
            conn.commit()
        except Exception as e:
            return False, str(e)
    return True, ""


def delete_location(location_id: int) -> Tuple[bool, str]:
    """Delete a location if it has no saved summaries."""
    if database.use_supabase():
        client = database.get_supabase_client()
        if client is None:
            return False, "Database unavailable"
        try:
            chk = (
                client.table(SUPABASE_DAILY_SUMMARY)
                .select("id", count="exact")
                .eq("location_id", location_id)
                .limit(1)
                .execute()
            )
            if (chk.count or 0) > 0:
                return False, "Location has saved data; delete summaries first."
            client.table("locations").delete().eq("id", location_id).execute()
        except Exception as e:
            return False, str(e)
        return True, ""

    with database.db_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            f"SELECT COUNT(*) FROM {SQLITE_DAILY_SUMMARIES} WHERE location_id = ?",
            (location_id,),
        )
        if int(cur.fetchone()[0]) > 0:
            return False, "Location has saved data; delete summaries first."
        cur.execute("DELETE FROM locations WHERE id = ?", (location_id,))
        conn.commit()
    return True, ""


def update_location_settings(location_id: int, settings: Dict[str, Any]) -> None:
    """Update mutable fields on locations."""
    allowed = {
        "name",
        "target_monthly_sales",
        "target_daily_sales",
        "seat_count",
    }
    payload = {k: v for k, v in settings.items() if k in allowed}
    if not payload:
        return

    if "name" in payload:
        new_name = str(payload["name"]).strip()
        if database.use_supabase():
            client = database.get_supabase_client()
            if client is None:
                raise RuntimeError("Supabase client not available")
            dup = (
                client.table("locations")
                .select("id")
                .eq("name", new_name)
                .neq("id", location_id)
                .limit(1)
                .execute()
            )
            if dup.data:
                raise ValueError(f"A location named '{new_name}' already exists")
        else:
            with database.db_connection() as conn:
                row = conn.execute(
                    "SELECT id FROM locations WHERE name = ? AND id != ?",
                    (new_name, location_id),
                ).fetchone()
                if row:
                    raise ValueError(f"A location named '{new_name}' already exists")

    if database.use_supabase():
        client = database.get_supabase_client()
        if client is None:
            raise RuntimeError("Supabase client not available")
        try:
            client.table("locations").update(payload).eq("id", location_id).execute()
        except Exception as e:
            err = str(e).lower()
            if "unique" in err or "duplicate" in err:
                raise ValueError(
                    f"A location named '{payload.get('name', '')}' already exists"
                ) from e
            raise
        return

    cols = ", ".join(f"{k} = ?" for k in payload)
    vals = list(payload.values()) + [location_id]
    try:
        with database.db_connection() as conn:
            conn.execute(f"UPDATE locations SET {cols} WHERE id = ?", vals)
            conn.commit()
    except Exception as e:
        if "UNIQUE constraint failed" in str(e):
            raise ValueError(f"A location named '{payload.get('name', '')}' already exists") from e
        raise
