"""Write/update/delete operations for the database layer."""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import config
import database


def save_daily_summary(location_id: int, data: Dict) -> int:
    """Save or update daily summary using INSERT OR REPLACE for atomic upsert."""
    database.logger.info(
        "Saving daily summary for location_id=%s date=%s",
        location_id,
        data.get("date"),
    )
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
            cursor.execute("DELETE FROM item_sales WHERE summary_id = ?", (summary_id,))
            for item in data["top_items"]:
                cursor.execute(
                    """
                    INSERT INTO item_sales (summary_id, item_name, qty, amount)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        summary_id,
                        item.get("item_name", ""),
                        item.get("qty", 0),
                        item.get("amount", 0),
                    ),
                )

        conn.commit()
        return summary_id


def ensure_default_locations() -> None:
    """Ensure Boteco default locations exist."""
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
    return True, f"Location '{name}' created."


def delete_location(location_id: int) -> Tuple[bool, str]:
    """Delete a location when it has no saved summaries."""
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
    return True, f"Location '{name}' deleted."


def update_location_settings(location_id: int, settings: Dict) -> None:
    """Update location settings."""
    allowed_cols = {"name", "target_monthly_sales", "target_daily_sales", "seat_count"}
    with database.db_connection() as conn:
        cursor = conn.cursor()
        updates = []
        vals = []
        if "name" in settings and settings["name"] is not None:
            updates.append("name = ?")
            vals.append(settings["name"])
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


def save_upload_record(
    location_id: int,
    date: str,
    filename: str,
    file_type: str,
    uploaded_by: str,
) -> None:
    """Save upload record."""
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
        cursor.execute("DELETE FROM category_sales WHERE summary_id = ?", (summary_id,))
        cursor.execute("DELETE FROM service_sales  WHERE summary_id = ?", (summary_id,))
        cursor.execute("DELETE FROM item_sales     WHERE summary_id = ?", (summary_id,))
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
            (covers, lunch_covers, dinner_covers, apc, turns, pct_target, summary_id),
        )
        conn.commit()
        return True


def wipe_all_data() -> Tuple[Dict[str, int], List[str]]:
    """Delete all operational data tables."""
    counts: Dict[str, int] = {}
    errors: List[str] = []
    with database.db_connection() as conn:
        cursor = conn.cursor()
        for table in [
            "item_sales",
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
