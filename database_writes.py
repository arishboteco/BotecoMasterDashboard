"""Write/update/delete operations for the database layer."""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, List, Optional, Tuple

import config
import database
from database_reads import get_all_locations, get_location_settings


def save_daily_summary(location_id: int, data: Dict) -> int:
    """Save or update daily summary using INSERT OR REPLACE for atomic upsert."""
    database.logger.info(
        "Saving daily summary for location_id=%s date=%s",
        location_id,
        data.get("date"),
    )

    if database.use_supabase():
        supabase = database.get_supabase_client()

        row_data = {
            "location_id": location_id,
            "date": data["date"],
            "covers": data.get("covers", 0),
            "turns": data.get("turns", 0),
            "gross_total": data.get("gross_total", 0),
            "net_total": data.get("net_total", 0),
            "cash_sales": data.get("cash_sales", 0),
            "card_sales": data.get("card_sales", 0),
            "gpay_sales": data.get("gpay_sales", 0),
            "zomato_sales": data.get("zomato_sales", 0),
            "other_sales": data.get("other_sales", 0),
            "service_charge": data.get("service_charge", 0),
            "cgst": data.get("cgst", 0),
            "sgst": data.get("sgst", 0),
            "discount": data.get("discount", 0),
            "complimentary": data.get("complimentary", 0),
            "apc": data.get("apc", 0),
            "target": data.get("target", 0),
            "pct_target": data.get("pct_target", 0),
            "mtd_total_covers": data.get("mtd_total_covers", 0),
            "mtd_net_sales": data.get("mtd_net_sales", 0),
            "mtd_discount": data.get("mtd_discount", 0),
            "mtd_avg_daily": data.get("mtd_avg_daily", 0),
            "mtd_target": data.get("mtd_target", 0),
            "mtd_pct_target": data.get("mtd_pct_target", 0),
            "lunch_covers": data.get("lunch_covers"),
            "dinner_covers": data.get("dinner_covers"),
            "order_count": data.get("order_count"),
        }

        existing = (
            supabase.table("daily_summaries")
            .select("id")
            .eq("location_id", location_id)
            .eq("date", data["date"])
            .execute()
        )

        if existing.data:
            summary_id = existing.data[0]["id"]
            supabase.table("daily_summaries").update(row_data).eq(
                "id", summary_id
            ).execute()
        else:
            result = supabase.table("daily_summaries").insert(row_data).execute()
            summary_id = result.data[0]["id"]

        if "categories" in data:
            supabase.table("category_sales").delete().eq(
                "summary_id", summary_id
            ).execute()
            if data["categories"]:
                cat_records = [
                    {
                        "summary_id": summary_id,
                        "category": cat["category"],
                        "qty": cat.get("qty", 0),
                        "amount": cat.get("amount", 0),
                    }
                    for cat in data["categories"]
                ]
                supabase.table("category_sales").insert(cat_records).execute()

        if "super_categories" in data:
            supabase.table("super_category_sales").delete().eq(
                "summary_id", summary_id
            ).execute()
            if data["super_categories"]:
                scat_records = [
                    {
                        "summary_id": summary_id,
                        "category": cat["category"],
                        "qty": cat.get("qty", 0),
                        "amount": cat.get("amount", 0),
                    }
                    for cat in data["super_categories"]
                ]
                supabase.table("super_category_sales").insert(scat_records).execute()

        if "services" in data:
            supabase.table("service_sales").delete().eq(
                "summary_id", summary_id
            ).execute()
            if data["services"]:
                svc_records = [
                    {
                        "summary_id": summary_id,
                        "service_type": svc["type"],
                        "amount": svc.get("amount", 0),
                    }
                    for svc in data["services"]
                ]
                supabase.table("service_sales").insert(svc_records).execute()

        if "top_items" in data and data["top_items"]:
            supabase.table("item_sales").delete().eq("summary_id", summary_id).execute()
            item_records = [
                {
                    "summary_id": summary_id,
                    "item_name": item.get("item_name", ""),
                    "category": item.get("category", ""),
                    "qty": item.get("qty", 0),
                    "amount": item.get("amount", 0),
                }
                for item in data["top_items"]
            ]
            supabase.table("item_sales").insert(item_records).execute()

        return summary_id
    else:
        with database.db_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT OR REPLACE INTO daily_summaries (
                    location_id, date, covers, turns, gross_total, net_total,
                    cash_sales, card_sales, gpay_sales, zomato_sales, other_sales,
                    service_charge, cgst, sgst, discount, complimentary, apc,
                    target, pct_target, mtd_total_covers, mtd_net_sales,
                    mtd_discount, mtd_avg_daily, mtd_target, mtd_pct_target,
                    lunch_covers, dinner_covers, order_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    location_id,
                    data["date"],
                    data.get("covers", 0),
                    data.get("turns", 0),
                    data.get("gross_total", 0),
                    data.get("net_total", 0),
                    data.get("cash_sales", 0),
                    data.get("card_sales", 0),
                    data.get("gpay_sales", 0),
                    data.get("zomato_sales", 0),
                    data.get("other_sales", 0),
                    data.get("service_charge", 0),
                    data.get("cgst", 0),
                    data.get("sgst", 0),
                    data.get("discount", 0),
                    data.get("complimentary", 0),
                    data.get("apc", 0),
                    data.get("target", 0),
                    data.get("pct_target", 0),
                    data.get("mtd_total_covers", 0),
                    data.get("mtd_net_sales", 0),
                    data.get("mtd_discount", 0),
                    data.get("mtd_avg_daily", 0),
                    data.get("mtd_target", 0),
                    data.get("mtd_pct_target", 0),
                    data.get("lunch_covers"),
                    data.get("dinner_covers"),
                    data.get("order_count"),
                ),
            )

            cursor.execute(
                "SELECT id FROM daily_summaries WHERE location_id = ? AND date = ?",
                (location_id, data["date"]),
            )
            summary_id = cursor.fetchone()["id"]

            if "categories" in data:
                cursor.execute(
                    "DELETE FROM category_sales WHERE summary_id = ?",
                    (summary_id,),
                )
                for cat in data["categories"]:
                    cursor.execute(
                        """
                        INSERT INTO category_sales (summary_id, category, qty, amount)
                        VALUES (?, ?, ?, ?)
                        """,
                        (
                            summary_id,
                            cat["category"],
                            cat.get("qty", 0),
                            cat.get("amount", 0),
                        ),
                    )

            if "super_categories" in data:
                cursor.execute(
                    "DELETE FROM super_category_sales WHERE summary_id = ?",
                    (summary_id,),
                )
                for cat in data["super_categories"]:
                    cursor.execute(
                        """
                        INSERT INTO super_category_sales (summary_id, category, qty, amount)
                        VALUES (?, ?, ?, ?)
                        """,
                        (
                            summary_id,
                            cat["category"],
                            cat.get("qty", 0),
                            cat.get("amount", 0),
                        ),
                    )

            if "services" in data:
                cursor.execute(
                    "DELETE FROM service_sales WHERE summary_id = ?",
                    (summary_id,),
                )
                for svc in data["services"]:
                    cursor.execute(
                        """
                        INSERT INTO service_sales (summary_id, service_type, amount)
                        VALUES (?, ?, ?)
                        """,
                        (summary_id, svc["type"], svc.get("amount", 0)),
                    )

            if "top_items" in data and data["top_items"]:
                cursor.execute(
                    "DELETE FROM item_sales WHERE summary_id = ?", (summary_id,)
                )
                for item in data["top_items"]:
                    cursor.execute(
                        """
                        INSERT INTO item_sales (summary_id, item_name, category, qty, amount)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (
                            summary_id,
                            item.get("item_name", ""),
                            item.get("category", ""),
                            item.get("qty", 0),
                            item.get("amount", 0),
                        ),
                    )

            conn.commit()
            return summary_id


def ensure_default_locations() -> None:
    """Ensure Boteco default locations exist."""
    if database.use_supabase():
        supabase = database.get_supabase_client()
        for name in ("Boteco - Indiqube", "Boteco - Bagmane"):
            existing = (
                supabase.table("locations").select("id").eq("name", name).execute()
            )
            if not existing.data:
                supabase.table("locations").insert(
                    {
                        "name": name,
                        "target_monthly_sales": config.MONTHLY_TARGET,
                        "target_daily_sales": config.DAILY_TARGET,
                    }
                ).execute()
    else:
        with database.db_connection() as conn:
            cursor = conn.cursor()
            for name in ("Boteco - Indiqube", "Boteco - Bagmane"):
                cursor.execute("SELECT id FROM locations WHERE name = ?", (name,))
                if cursor.fetchone() is None:
                    cursor.execute(
                        """
                        INSERT INTO locations (name, target_monthly_sales, target_daily_sales)
                        VALUES (?, ?, ?)
                        """,
                        (name, config.MONTHLY_TARGET, config.DAILY_TARGET),
                    )
            conn.commit()


def create_location(
    name: str,
    monthly_target: float = 5_000_000,
    seat_count: Optional[int] = None,
) -> Tuple[bool, str]:
    """Add a new outlet location."""
    if not name.strip():
        return False, "Location name cannot be empty."

    if database.use_supabase():
        supabase = database.get_supabase_client()
        existing = (
            supabase.table("locations").select("id").eq("name", name.strip()).execute()
        )
        if existing.data:
            return False, f"Location '{name}' already exists."
        daily = monthly_target / 30.0
        supabase.table("locations").insert(
            {
                "name": name.strip(),
                "target_monthly_sales": monthly_target,
                "target_daily_sales": daily,
                "seat_count": seat_count,
            }
        ).execute()
        get_all_locations.clear()
        return True, f"Location '{name}' created."
    else:
        with database.db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM locations WHERE name = ?", (name.strip(),))
            if cursor.fetchone():
                return False, f"Location '{name}' already exists."
            daily = monthly_target / 30.0
            cursor.execute(
                """
                INSERT INTO locations (name, target_monthly_sales, target_daily_sales, seat_count)
                VALUES (?, ?, ?, ?)
                """,
                (name.strip(), monthly_target, daily, seat_count),
            )
            conn.commit()
        get_all_locations.clear()
        return True, f"Location '{name}' created."


def delete_location(location_id: int) -> Tuple[bool, str]:
    """Delete a location when it has no saved summaries."""
    if database.use_supabase():
        supabase = database.get_supabase_client()
        result = (
            supabase.table("locations").select("name").eq("id", location_id).execute()
        )
        if not result.data:
            return False, "Location not found."
        name = result.data[0]["name"]

        summary_count = (
            supabase.table("daily_summaries")
            .select("id", count="exact")
            .eq("location_id", location_id)
            .execute()
        )
        if summary_count.count > 0:
            return (
                False,
                f"Cannot delete '{name}' — it has {summary_count.count} saved day(s) of data. "
                "Remove all data first or archive the location instead.",
            )
        supabase.table("locations").delete().eq("id", location_id).execute()
        get_all_locations.clear()
        get_location_settings.clear()
        return True, f"Location '{name}' deleted."
    else:
        with database.db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM locations WHERE id = ?", (location_id,))
            row = cursor.fetchone()
            if not row:
                return False, "Location not found."
            name = row["name"]
            cursor.execute(
                "SELECT COUNT(*) AS n FROM daily_summaries WHERE location_id = ?",
                (location_id,),
            )
            count = cursor.fetchone()["n"]
            if count > 0:
                return (
                    False,
                    f"Cannot delete '{name}' — it has {count} saved day(s) of data. "
                    "Remove all data first or archive the location instead.",
                )
            cursor.execute("DELETE FROM locations WHERE id = ?", (location_id,))
            conn.commit()
        get_all_locations.clear()
        get_location_settings.clear()
        return True, f"Location '{name}' deleted."


def update_location_settings(location_id: int, settings: Dict) -> None:
    """Update location settings."""
    allowed_cols = {"name", "target_monthly_sales", "target_daily_sales", "seat_count"}

    if database.use_supabase():
        supabase = database.get_supabase_client()
        updates = {}

        if "name" in settings and settings["name"] is not None:
            name = str(settings["name"]).strip()
            if not name:
                raise ValueError("Location name cannot be empty.")
            existing = (
                supabase.table("locations")
                .select("id")
                .eq("name", name)
                .neq("id", location_id)
                .execute()
            )
            if existing.data:
                raise ValueError(f"Location name '{name}' already exists.")
            updates["name"] = name

        if (
            "target_monthly_sales" in settings
            and settings["target_monthly_sales"] is not None
        ):
            updates["target_monthly_sales"] = settings["target_monthly_sales"]
            updates["target_daily_sales"] = (
                float(settings["target_monthly_sales"]) / 30.0
            )

        if "seat_count" in settings:
            updates["seat_count"] = settings["seat_count"]

        if updates:
            for col in updates.keys():
                if col not in allowed_cols:
                    raise ValueError(f"Invalid column name: {col}")
            supabase.table("locations").update(updates).eq("id", location_id).execute()
            get_location_settings.clear()
            get_all_locations.clear()
    else:
        with database.db_connection() as conn:
            cursor = conn.cursor()
            updates = []
            vals = []
            if "name" in settings and settings["name"] is not None:
                name = str(settings["name"]).strip()
                if not name:
                    raise ValueError("Location name cannot be empty.")
                cursor.execute(
                    "SELECT id FROM locations WHERE name = ? AND id != ?",
                    (name, location_id),
                )
                if cursor.fetchone() is not None:
                    raise ValueError(f"Location name '{name}' already exists.")
                updates.append("name = ?")
                vals.append(name)
            if (
                "target_monthly_sales" in settings
                and settings["target_monthly_sales"] is not None
            ):
                updates.append("target_monthly_sales = ?")
                vals.append(settings["target_monthly_sales"])
                updates.append("target_daily_sales = ?")
                vals.append(float(settings["target_monthly_sales"]) / 30.0)
            if "seat_count" in settings:
                updates.append("seat_count = ?")
                vals.append(settings["seat_count"])
            if updates:
                for col in updates:
                    col_name = col.split(" = ")[0]
                    if col_name not in allowed_cols:
                        raise ValueError(f"Invalid column name: {col_name}")
                vals.append(location_id)
                cursor.execute(
                    f"UPDATE locations SET {', '.join(updates)} WHERE id = ?",
                    vals,
                )
            conn.commit()
            get_location_settings.clear()
            get_all_locations.clear()


def save_upload_record(
    location_id: int,
    date: str,
    filename: str,
    file_type: str,
    uploaded_by: str,
) -> None:
    """Save upload record."""
    if database.use_supabase():
        supabase = database.get_supabase_client()
        supabase.table("upload_history").insert(
            {
                "location_id": location_id,
                "date": date,
                "filename": filename,
                "file_type": file_type,
                "uploaded_by": uploaded_by,
            }
        ).execute()
    else:
        with database.db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO upload_history (location_id, date, filename, file_type, uploaded_by)
                VALUES (?, ?, ?, ?, ?)
                """,
                (location_id, date, filename, file_type, uploaded_by),
            )
            conn.commit()


def delete_daily_summary_for_location_date(location_id: int, date: str) -> bool:
    """Remove one day summary and its child rows."""
    database.logger.info(
        "Deleting daily summary for location_id=%s date=%s", location_id, date
    )

    if database.use_supabase():
        supabase = database.get_supabase_client()
        result = (
            supabase.table("daily_summaries")
            .select("id")
            .eq("location_id", location_id)
            .eq("date", date)
            .execute()
        )

        if not result.data:
            return False

        summary_id = result.data[0]["id"]
        supabase.table("category_sales").delete().eq("summary_id", summary_id).execute()
        supabase.table("super_category_sales").delete().eq(
            "summary_id", summary_id
        ).execute()
        supabase.table("service_sales").delete().eq("summary_id", summary_id).execute()
        supabase.table("item_sales").delete().eq("summary_id", summary_id).execute()
        supabase.table("daily_summaries").delete().eq("id", summary_id).execute()
        return True
    else:
        with database.db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id FROM daily_summaries WHERE location_id = ? AND date = ?",
                (location_id, date),
            )
            row = cursor.fetchone()
            if not row:
                return False
            summary_id = row["id"]
            cursor.execute(
                "DELETE FROM category_sales WHERE summary_id = ?", (summary_id,)
            )
            cursor.execute(
                "DELETE FROM super_category_sales WHERE summary_id = ?", (summary_id,)
            )
            cursor.execute(
                "DELETE FROM service_sales  WHERE summary_id = ?", (summary_id,)
            )
            cursor.execute(
                "DELETE FROM item_sales     WHERE summary_id = ?", (summary_id,)
            )
            cursor.execute("DELETE FROM daily_summaries WHERE id = ?", (summary_id,))
            conn.commit()
            return True


def update_daily_summary_covers_only(
    location_id: int,
    date: str,
    covers: int,
    lunch_covers: Optional[int] = None,
    dinner_covers: Optional[int] = None,
) -> bool:
    """Update covers fields on an existing row."""
    if database.use_supabase():
        supabase = database.get_supabase_client()
        result = (
            supabase.table("daily_summaries")
            .select("id, net_total, target, locations(seat_count)")
            .eq("location_id", location_id)
            .eq("date", date)
            .execute()
        )

        if not result.data:
            return False

        row = result.data[0]
        summary_id = row["id"]
        net = float(row["net_total"] or 0)
        tgt = float(row["target"] or 0)
        apc = (net / covers) if covers > 0 and net > 0 else 0.0
        seats = (
            row.get("locations", {}).get("seat_count")
            if isinstance(row.get("locations"), dict)
            else None
        )
        if seats and int(seats) > 0:
            turns = round(covers / float(seats), 2)
        else:
            turns = round(covers / 100, 1) if covers else 0.0
        pct_target = round((net / tgt) * 100, 2) if tgt > 0 else 0.0

        supabase.table("daily_summaries").update(
            {
                "covers": covers,
                "lunch_covers": lunch_covers,
                "dinner_covers": dinner_covers,
                "apc": apc,
                "turns": turns,
                "pct_target": pct_target,
            }
        ).eq("id", summary_id).execute()
        return True
    else:
        with database.db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT ds.id, ds.net_total, ds.target, loc.seat_count AS seat_count
                FROM daily_summaries ds
                LEFT JOIN locations loc ON loc.id = ds.location_id
                WHERE ds.location_id = ? AND ds.date = ?
                """,
                (location_id, date),
            )
            row = cursor.fetchone()
            if not row:
                return False
            summary_id = row["id"]
            net = float(row["net_total"] or 0)
            tgt = float(row["target"] or 0)
            apc = (net / covers) if covers > 0 and net > 0 else 0.0
            seats = row["seat_count"]
            if seats and int(seats) > 0:
                turns = round(covers / float(seats), 2)
            else:
                turns = round(covers / 100, 1) if covers else 0.0
            pct_target = round((net / tgt) * 100, 2) if tgt > 0 else 0.0
            cursor.execute(
                """
                UPDATE daily_summaries SET
                    covers = ?, lunch_covers = ?, dinner_covers = ?,
                    apc = ?, turns = ?, pct_target = ?
                WHERE id = ?
                """,
                (
                    covers,
                    lunch_covers,
                    dinner_covers,
                    apc,
                    turns,
                    pct_target,
                    summary_id,
                ),
            )
            conn.commit()
            return True


def wipe_all_data() -> Tuple[Dict[str, int], List[str]]:
    """Delete all operational data tables."""
    counts: Dict[str, int] = {}
    errors: List[str] = []

    if database.use_supabase():
        supabase = (
            database.get_supabase_admin_client() or database.get_supabase_client()
        )
        if supabase is None:
            errors.append("Supabase client unavailable")
            return counts, errors
        is_admin = database.get_supabase_admin_client() is not None
        if not is_admin:
            errors.append(
                "WARNING: Using anon key — Supabase RLS may block deletes. "
                "Set SUPABASE_SERVICE_KEY env variable for admin-level access."
            )
        for table in [
            "item_sales",
            "super_category_sales",
            "category_sales",
            "service_sales",
            "daily_summaries",
            "upload_history",
        ]:
            try:
                delete_result = supabase.table(table).delete().gt("id", -1).execute()
                actual_deleted = len(delete_result.data) if hasattr(delete_result, "data") else 0
                counts[table] = actual_deleted
            except Exception as e:
                counts[table] = 0
                errors.append(f"{table}: {e}")
    else:
        with database.db_connection() as conn:
            cursor = conn.cursor()
            for table in [
                "item_sales",
                "super_category_sales",
                "category_sales",
                "service_sales",
                "daily_summaries",
                "upload_history",
            ]:
                try:
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    count = cursor.fetchone()[0]
                    cursor.execute(f"DELETE FROM {table}")
                    counts[table] = count
                except Exception as e:
                    counts[table] = 0
                    errors.append(f"{table}: {e}")
            conn.commit()

    total = sum(counts.values())
    database.logger.info(
        f"Wiped all data: {total} records deleted across {len(counts)} tables"
    )
    if errors:
        database.logger.warning(f"Errors during wipe: {errors}")
    return counts, errors


def backfill_weekday_weighted_targets() -> Tuple[int, int]:
    """Recompute and overwrite the target column for all existing daily_summaries rows.

    Uses 8 weeks of history per location to derive a weekday mix, then applies
    that mix to each row's monthly target to get a day-specific target.

    Returns (updated_count, locations_processed). Safe to re-run — is idempotent
    per location (each location's rows are fully overwritten with its own mix).
    """
    import utils

    if database.use_supabase():
        supabase = database.get_supabase_client()

        meta = (
            supabase.table("app_meta")
            .select("k")
            .eq("k", "weekday_target_backfill")
            .execute()
        )
        if meta.data:
            database.logger.info("weekday_target_backfill already run, skipping.")
            return 0, 0

        locations_result = (
            supabase.table("daily_summaries").select("location_id").execute()
        )
        location_ids = list(set(row["location_id"] for row in locations_result.data))

        if not location_ids:
            return 0, 0

        recent_result = (
            supabase.table("daily_summaries")
            .select("location_id, date, net_total")
            .in_("location_id", location_ids)
            .order("date", desc=True)
            .execute()
        )

        recent_by_loc: Dict[int, List[Dict]] = defaultdict(list)
        for row in recent_result.data:
            recent_by_loc[row["location_id"]].append(row)

        loc_settings_by_id: Dict[int, Optional[Dict]] = {}
        for lid in location_ids:
            st = database.get_location_settings(lid)
            loc_settings_by_id[lid] = st

        day_targets_by_loc: Dict[int, dict] = {}
        for loc_id in location_ids:
            recent = recent_by_loc.get(loc_id, [])
            weekday_mix = utils.compute_weekday_mix(recent)
            st = loc_settings_by_id[loc_id]
            monthly = (
                float(st["target_monthly_sales"])
                if st and st.get("target_monthly_sales")
                else float(config.MONTHLY_TARGET)
            )
            day_targets_by_loc[loc_id] = utils.compute_day_targets(monthly, weekday_mix)

        all_rows_result = (
            supabase.table("daily_summaries")
            .select("id, date, location_id")
            .in_("location_id", location_ids)
            .order("location_id")
            .execute()
        )

        updated_total = 0
        for row in all_rows_result.data:
            loc_id = row["location_id"]
            new_target = utils.get_target_for_date(
                day_targets_by_loc[loc_id], row["date"]
            )
            supabase.table("daily_summaries").update({"target": new_target}).eq(
                "id", row["id"]
            ).execute()
            updated_total += 1

        supabase.table("app_meta").insert(
            {"k": "weekday_target_backfill", "v": "done"}
        ).execute()

        database.logger.info(
            f"backfill_weekday_weighted_targets complete: {updated_total} rows across {len(location_ids)} locations"
        )
        return updated_total, len(location_ids)
    else:
        with database.db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT k FROM app_meta WHERE k = ?", ("weekday_target_backfill",)
            )
            if cursor.fetchone():
                database.logger.info("weekday_target_backfill already run, skipping.")
                return 0, 0

        with database.db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT location_id FROM daily_summaries")
            location_ids = [row["location_id"] for row in cursor.fetchall()]

        if not location_ids:
            return 0, 0

        placeholders = ",".join("?" * len(location_ids))
        with database.db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"""
                SELECT location_id, date, net_total
                FROM daily_summaries
                WHERE location_id IN ({placeholders})
                ORDER BY location_id, date DESC
                """,
                list(location_ids),
            )
            recent_rows = cursor.fetchall()

        recent_by_loc: Dict[int, List[Dict]] = defaultdict(list)
        for row in recent_rows:
            recent_by_loc[row["location_id"]].append(dict(row))

        loc_settings_by_id: Dict[int, Optional[Dict]] = {}
        for lid in location_ids:
            st = database.get_location_settings(lid)
            loc_settings_by_id[lid] = st

        day_targets_by_loc: Dict[int, dict] = {}
        for loc_id in location_ids:
            recent = recent_by_loc.get(loc_id, [])
            weekday_mix = utils.compute_weekday_mix(recent)
            st = loc_settings_by_id[loc_id]
            monthly = (
                float(st["target_monthly_sales"])
                if st and st.get("target_monthly_sales")
                else float(config.MONTHLY_TARGET)
            )
            day_targets_by_loc[loc_id] = utils.compute_day_targets(monthly, weekday_mix)

        with database.db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"""
                SELECT id, date, location_id
                FROM daily_summaries
                WHERE location_id IN ({placeholders})
                ORDER BY location_id
                """,
                list(location_ids),
            )
            all_update_rows = cursor.fetchall()

        updated_total = 0
        locations_processed = len(location_ids)

        with database.db_connection() as conn:
            cursor = conn.cursor()
            for row in all_update_rows:
                loc_id = row["location_id"]
                new_target = utils.get_target_for_date(
                    day_targets_by_loc[loc_id], row["date"]
                )
                cursor.execute(
                    "UPDATE daily_summaries SET target = ? WHERE id = ?",
                    (new_target, row["id"]),
                )
                updated_total += 1
            conn.commit()

            cursor.execute(
                "INSERT OR REPLACE INTO app_meta (k, v) VALUES (?, ?)",
                ("weekday_target_backfill", "done"),
            )
            conn.commit()

        database.logger.info(
            f"backfill_weekday_weighted_targets complete: {updated_total} rows across {locations_processed} locations"
        )
        return updated_total, locations_processed
