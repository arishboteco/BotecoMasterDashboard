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
    SQLITE_PAYMENT_METHOD_SALES,
    SQLITE_SERVICE_SALES,
    SUPABASE_BILL_ITEMS,
    SUPABASE_CATEGORY_SUMMARY,
    SUPABASE_DAILY_SUMMARY,
    SUPABASE_PAYMENT_METHOD_SALES,
)

logger = get_logger(__name__)

LOCATION_ID_TO_RESTAURANT = {
    1: "Boteco",
    2: "Boteco - Bagmane",
}

# PostgREST performs best with modest payload sizes; large CSVs are split across requests.
_SUPABASE_ROW_CHUNK = 500


def ensure_default_locations() -> None:
    """Ensure default outlets exist (Supabase upsert; SQLite seed if DB is empty)."""
    if database.use_supabase():
        from database import get_supabase_client

        client = get_supabase_client()
        if client is None:
            return
        try:
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
        except Exception as exc:
            error_text = str(exc).lower()
            is_rls_error = (
                "row-level security policy" in error_text or "code': '42501'" in error_text
            )
            if is_rls_error:
                logger.info(
                    "Skipping default location seed for Supabase due to RLS policy restrictions."
                )
            else:
                logger.warning(
                    "Skipping default location seed for Supabase due to unexpected error.",
                    exc_info=True,
                )
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


def build_daily_summary_row_new_flow(
    location_id: int, date: str, data: Dict[str, Any]
) -> Dict[str, Any]:
    """Build a daily_summary dict for the new Growth Report flow.

    Includes all legacy fields plus the new fields added in the schema migration.
    Caller passes this to upsert_daily_summaries_supabase_batch.
    """
    return {
        "location_id": location_id,
        "date": date,
        # Core financials
        "gross_total": round(float(data.get("gross_total", 0) or 0), 2),
        "net_total": round(float(data.get("net_total", 0) or 0), 2),
        "covers": int(data.get("covers", 0) or 0),
        "discount": round(float(data.get("discount", 0) or 0), 2),
        "cgst": round(float(data.get("cgst", 0) or 0), 2),
        "sgst": round(float(data.get("sgst", 0) or 0), 2),
        "service_charge": round(float(data.get("service_charge", 0) or 0), 2),
        "gst_on_service_charge": round(float(data.get("gst_on_service_charge", 0) or 0), 2),
        "cancelled_amount": round(float(data.get("cancelled_amount", 0) or 0), 2),
        "complementary_amount": round(float(data.get("complementary_amount", 0) or 0), 2),
        "order_count": int(data.get("order_count", 0) or 0),
        # Legacy payment fields (kept for backward compat; zomato/other always 0 in new flow)
        "cash_sales": round(float(data.get("cash_sales", 0) or 0), 2),
        "card_sales": round(float(data.get("card_sales", 0) or 0), 2),
        "gpay_sales": round(float(data.get("gpay_sales", 0) or 0), 2),
        "zomato_sales": round(float(data.get("zomato_sales", 0) or 0), 2),
        # Dynamic payment methods are stored in payment_method_sales; do not create new other_sales.
        # New fields from schema migration
        "my_amount": round(float(data.get("my_amount", 0) or 0), 2),
        "total_tax": round(float(data.get("total_tax", 0) or 0), 2),
        "round_off": round(float(data.get("round_off", 0) or 0), 2),
        "expenses": round(float(data.get("expenses", 0) or 0), 2),
        "due_payment_sales": round(float(data.get("due_payment_sales", 0) or 0), 2),
        "wallet_sales": round(float(data.get("wallet_sales", 0) or 0), 2),
        "upi_sales": round(float(data.get("upi_sales", 0) or 0), 2),
        "bank_transfer_sales": round(float(data.get("bank_transfer_sales", 0) or 0), 2),
        "boh_sales": round(float(data.get("boh_sales", 0) or 0), 2),
        "delivery_sales": round(float(data.get("delivery_sales", 0) or 0), 2),
        "pickup_sales": round(float(data.get("pickup_sales", 0) or 0), 2),
        "dine_in_sales": round(float(data.get("dine_in_sales", 0) or 0), 2),
        "menu_qr_sales": round(float(data.get("menu_qr_sales", 0) or 0), 2),
        "source_report": str(data.get("source_report", "growth_report_day_wise")),
    }


def upsert_daily_summary_supabase(
    supabase: Any, location_id: int, date: str, data: Dict[str, Any]
) -> int:
    """Upsert one row in public.daily_summary (Supabase)."""
    row_data = build_daily_summary_row_new_flow(location_id, date, data)
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


def save_payment_method_sales_batch(supabase: Any, rows: List[Dict[str, Any]]) -> None:
    """Bulk upsert normalized payment-method rows."""
    if not rows:
        return
    normalized = []
    for row in rows:
        amount = round(float(row.get("amount", 0) or 0), 2)
        if abs(amount) < 0.005:
            continue
        normalized.append(
            {
                "location_id": int(row["location_id"]),
                "date": str(row["date"]),
                "payment_method": str(row["payment_method"]),
                "payment_key": str(row["payment_key"]),
                "amount": amount,
                "source_report": str(row.get("source_report", "growth_report_day_wise")),
            }
        )
    for i in range(0, len(normalized), _SUPABASE_ROW_CHUNK):
        chunk = normalized[i : i + _SUPABASE_ROW_CHUNK]
        supabase.table(SUPABASE_PAYMENT_METHOD_SALES).upsert(
            chunk, on_conflict="location_id,date,payment_key"
        ).execute()


def delete_payment_method_sales_batch(supabase: Any, dates_locs: set) -> None:
    """Delete normalized payment-method rows for date/location pairs before reimport."""
    for date_str, loc_id in sorted(dates_locs):
        supabase.table(SUPABASE_PAYMENT_METHOD_SALES).delete().eq("date", date_str).eq(
            "location_id", loc_id
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
    turns_raw = data.get("turns")
    turns_value = round(float(turns_raw), 1) if turns_raw is not None else 0.0

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
                    turns_value,
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
                    turns_value,
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
        cur.execute(
            f"DELETE FROM {SQLITE_PAYMENT_METHOD_SALES} WHERE location_id = ? AND date = ?",
            (location_id, date_str),
        )

        item_rows: List[tuple] = []
        for cat in data.get("categories") or []:
            name = str(cat.get("category", "") or "").strip()
            if not name:
                continue
            item_rows.append(
                (
                    summary_id,
                    f"{CATEGORY_ROW_PREFIX}{name}",
                    name,
                    int(cat.get("qty", 0) or 0),
                    float(cat.get("amount", 0) or 0),
                )
            )
        for item in data.get("top_items") or []:
            iname = str(item.get("item_name", "") or "").strip()
            if not iname:
                continue
            item_rows.append(
                (
                    summary_id,
                    iname,
                    str(item.get("category", "") or ""),
                    int(item.get("qty", 0) or 0),
                    float(item.get("amount", 0) or 0),
                )
            )
        if item_rows:
            cur.executemany(
                f"""
                INSERT INTO {SQLITE_ITEM_SALES} (summary_id, item_name, category, qty, amount)
                VALUES (?, ?, ?, ?, ?)
                """,
                item_rows,
            )

        service_rows: List[tuple] = []
        for svc in data.get("services") or []:
            stype = str(svc.get("type", "") or "").strip()
            if not stype:
                continue
            service_rows.append((summary_id, stype, float(svc.get("amount", 0) or 0)))
        if service_rows:
            cur.executemany(
                f"""
                INSERT INTO {SQLITE_SERVICE_SALES} (summary_id, service_type, amount)
                VALUES (?, ?, ?)
                """,
                service_rows,
            )

        payment_rows: List[tuple] = []
        for method in data.get("payment_methods") or []:
            amount = round(float(method.get("amount", 0) or 0), 2)
            if abs(amount) < 0.005:
                continue
            payment_rows.append(
                (
                    location_id,
                    date_str,
                    str(method.get("payment_method", "") or "").strip(),
                    str(method.get("payment_key", "") or "").strip(),
                    amount,
                    str(method.get("source_report", "growth_report_day_wise")),
                )
            )
        if payment_rows:
            cur.executemany(
                f"""
                INSERT INTO {SQLITE_PAYMENT_METHOD_SALES} (
                    location_id, date, payment_method, payment_key, amount, source_report
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                payment_rows,
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
    """Bulk upsert category_summary records (Supabase), chunked.

    Supports both legacy rows (only location_id/date/category_name/net_amount/qty)
    and new-flow rows with the full expanded schema. Conflict must remain on
    (location_id, date, category_name) so multiple categories within the same
    normalized bucket (e.g. Liquor) are preserved.
    """
    if not records:
        return

    def _build(r: Dict[str, Any]) -> Dict[str, Any]:
        row: Dict[str, Any] = {
            "location_id": r["location_id"],
            "date": r["date"],
            "category_name": str(r.get("category_name", "") or ""),
            "net_amount": round(float(r.get("net_amount", 0) or 0), 2),
            "qty": int(r.get("qty", 0) or 0),
        }
        # New-flow fields — include only when present to avoid overwriting with nulls
        for field in (
            "group_name",
            "normalized_category",
            "sub_total",
            "discount",
            "tax",
            "final_total",
            "cgst_amount",
            "sgst_amount",
            "service_charge_amount",
            "complimentary_amount",
            "cancelled_amount",
            "source_report",
        ):
            if field in r and r[field] is not None:
                if isinstance(r[field], float):
                    row[field] = round(r[field], 2)
                else:
                    row[field] = r[field]
        # If normalized_category not present, fall back to category_name
        if "normalized_category" not in row:
            row["normalized_category"] = row["category_name"]
        return row

    normalized = [_build(r) for r in records]
    deduped_by_conflict: Dict[Tuple[int, str, str], Dict[str, Any]] = {}
    for row in normalized:
        key = (
            int(row["location_id"]),
            str(row["date"]),
            str(row.get("category_name") or ""),
        )
        # Keep the latest row for the conflict key to avoid
        # `ON CONFLICT DO UPDATE command cannot affect row a second time`.
        deduped_by_conflict[key] = row
    normalized = list(deduped_by_conflict.values())
    # Upsert on category_name to match schema unique constraint and retain
    # multiple categories that share one normalized_category.
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
    supabase.table(SUPABASE_BILL_ITEMS).delete().neq("id", 0).execute()
    supabase.table(SUPABASE_DAILY_SUMMARY).delete().neq("id", 0).execute()
    supabase.table(SUPABASE_CATEGORY_SUMMARY).delete().neq("id", 0).execute()
    supabase.table(SUPABASE_PAYMENT_METHOD_SALES).delete().neq("id", 0).execute()
    supabase.table("upload_history").delete().neq("id", 0).execute()


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
                SUPABASE_PAYMENT_METHOD_SALES,
                "upload_history",
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
            cur.execute(f"SELECT COUNT(*) FROM {SQLITE_PAYMENT_METHOD_SALES}")
            counts["payment_method_sales"] = int(cur.fetchone()[0])
            cur.execute("SELECT COUNT(*) FROM upload_history")
            counts["upload_history"] = int(cur.fetchone()[0])
            cur.execute(f"SELECT COUNT(*) FROM {SQLITE_DAILY_SUMMARIES}")
            counts["daily_summaries"] = int(cur.fetchone()[0])
            cur.execute(f"DELETE FROM {SQLITE_ITEM_SALES}")
            cur.execute(f"DELETE FROM {SQLITE_SERVICE_SALES}")
            cur.execute(f"DELETE FROM {SQLITE_PAYMENT_METHOD_SALES}")
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
    """Insert multiple upload_history rows in few round-trips.

    Supports both legacy rows (location_id/date/filename/file_type/uploaded_by)
    and new-flow rows with the expanded schema fields.
    """
    if not rows:
        return
    if database.use_supabase():
        client = database.get_supabase_client()
        if client is None:
            raise RuntimeError("Supabase client not available")

        def _build(r: Dict[str, Any]) -> Dict[str, Any]:
            base: Dict[str, Any] = {
                "location_id": int(r["location_id"]),
                "date": r.get("date"),
                "filename": r.get("filename", "unknown"),
                "file_type": r.get("file_type", "unknown"),
                "uploaded_by": r.get("uploaded_by", "user"),
            }
            for field in (
                "detected_location_name",
                "detected_report_type",
                "period_start",
                "period_end",
                "row_count",
                "status",
                "validation_errors",
                "import_summary",
                "file_hash",
            ):
                if field in r and r[field] is not None:
                    base[field] = r[field]
            return base

        payload = [_build(r) for r in rows]
        for i in range(0, len(payload), _SUPABASE_ROW_CHUNK):
            client.table("upload_history").insert(payload[i : i + _SUPABASE_ROW_CHUNK]).execute()
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
                    r.get("date"),
                    r.get("filename", "unknown"),
                    r.get("file_type", "unknown"),
                    r.get("uploaded_by", "user"),
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
