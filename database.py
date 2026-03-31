import sqlite3
import hashlib
import os
from datetime import datetime
from typing import Optional, List, Dict, Any
import config

# Handle both local and cloud deployment
DB_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_PATH = os.path.join(DB_DIR, "data", "boteco.db")

# Ensure data directory exists
os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)


def get_connection():
    """Get database connection with row factory."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_database():
    """Initialize database with all tables."""
    conn = get_connection()
    cursor = conn.cursor()

    # Locations table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS locations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            target_monthly_sales REAL DEFAULT 5000000,
            target_daily_sales REAL DEFAULT 166667,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            email TEXT,
            role TEXT DEFAULT 'manager',
            location_id INTEGER,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (location_id) REFERENCES locations(id)
        )
    """)

    # Daily summaries: composite UNIQUE(location_id, date) so each outlet has its own row per day
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS daily_summaries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            location_id INTEGER NOT NULL,
            date DATE NOT NULL,
            covers INTEGER DEFAULT 0,
            turns REAL DEFAULT 0,
            gross_total REAL DEFAULT 0,
            net_total REAL DEFAULT 0,
            cash_sales REAL DEFAULT 0,
            card_sales REAL DEFAULT 0,
            gpay_sales REAL DEFAULT 0,
            zomato_sales REAL DEFAULT 0,
            other_sales REAL DEFAULT 0,
            service_charge REAL DEFAULT 0,
            cgst REAL DEFAULT 0,
            sgst REAL DEFAULT 0,
            discount REAL DEFAULT 0,
            complimentary REAL DEFAULT 0,
            apc REAL DEFAULT 0,
            target REAL DEFAULT 166667,
            pct_target REAL DEFAULT 0,
            mtd_total_covers INTEGER DEFAULT 0,
            mtd_net_sales REAL DEFAULT 0,
            mtd_discount REAL DEFAULT 0,
            mtd_avg_daily REAL DEFAULT 0,
            mtd_target REAL DEFAULT 5000000,
            mtd_pct_target REAL DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (location_id) REFERENCES locations(id),
            UNIQUE(location_id, date)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS app_meta (
            k TEXT PRIMARY KEY,
            v TEXT NOT NULL
        )
    """)

    # Category sales table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS category_sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            summary_id INTEGER NOT NULL,
            category TEXT NOT NULL,
            qty INTEGER DEFAULT 0,
            amount REAL DEFAULT 0,
            FOREIGN KEY (summary_id) REFERENCES daily_summaries(id)
        )
    """)

    # Service sales table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS service_sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            summary_id INTEGER NOT NULL,
            service_type TEXT NOT NULL,
            amount REAL DEFAULT 0,
            FOREIGN KEY (summary_id) REFERENCES daily_summaries(id)
        )
    """)

    # Upload history table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS upload_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            location_id INTEGER NOT NULL,
            date DATE NOT NULL,
            filename TEXT,
            file_type TEXT,
            uploaded_by TEXT,
            uploaded_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (location_id) REFERENCES locations(id)
        )
    """)

    cursor.execute("PRAGMA table_info(daily_summaries)")
    _ds_cols = {row[1] for row in cursor.fetchall()}
    for _col, _typ in (("lunch_covers", "INTEGER"), ("dinner_covers", "INTEGER")):
        if _col not in _ds_cols:
            cursor.execute(
                f"ALTER TABLE daily_summaries ADD COLUMN {_col} {_typ} DEFAULT NULL"
            )

    cursor.execute("PRAGMA table_info(locations)")
    _loc_cols = {row[1] for row in cursor.fetchall()}
    if "seat_count" not in _loc_cols:
        cursor.execute(
            "ALTER TABLE locations ADD COLUMN seat_count INTEGER DEFAULT NULL"
        )

    _migrate_daily_summaries_composite_unique(cursor)

    conn.commit()
    conn.close()


def _migrate_daily_summaries_composite_unique(cursor) -> None:
    """One-time: replace global UNIQUE(date) with UNIQUE(location_id, date). Preserves ids for FK children."""
    cursor.execute("SELECT v FROM app_meta WHERE k = ?", ("ds_composite_unique",))
    if cursor.fetchone():
        return
    cursor.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='daily_summaries'"
    )
    row = cursor.fetchone()
    if not row or not row[0]:
        cursor.execute(
            "INSERT OR REPLACE INTO app_meta (k, v) VALUES (?, ?)",
            ("ds_composite_unique", "1"),
        )
        return
    sql_create = row[0].lower()
    if "unique(location_id, date)" in sql_create.replace(" ", ""):
        cursor.execute(
            "INSERT OR REPLACE INTO app_meta (k, v) VALUES (?, ?)",
            ("ds_composite_unique", "1"),
        )
        return
    # Legacy: date was globally UNIQUE — only one row per calendar date
    if "date" not in sql_create:
        return

    cursor.execute("DROP TABLE IF EXISTS daily_summaries_new")

    cursor.execute("PRAGMA table_info(daily_summaries)")
    col_rows = cursor.fetchall()
    col_names = [c[1] for c in col_rows]

    cursor.execute(
        """
        CREATE TABLE daily_summaries_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            location_id INTEGER NOT NULL,
            date DATE NOT NULL,
            covers INTEGER DEFAULT 0,
            turns REAL DEFAULT 0,
            gross_total REAL DEFAULT 0,
            net_total REAL DEFAULT 0,
            cash_sales REAL DEFAULT 0,
            card_sales REAL DEFAULT 0,
            gpay_sales REAL DEFAULT 0,
            zomato_sales REAL DEFAULT 0,
            other_sales REAL DEFAULT 0,
            service_charge REAL DEFAULT 0,
            cgst REAL DEFAULT 0,
            sgst REAL DEFAULT 0,
            discount REAL DEFAULT 0,
            complimentary REAL DEFAULT 0,
            apc REAL DEFAULT 0,
            target REAL DEFAULT 166667,
            pct_target REAL DEFAULT 0,
            mtd_total_covers INTEGER DEFAULT 0,
            mtd_net_sales REAL DEFAULT 0,
            mtd_discount REAL DEFAULT 0,
            mtd_avg_daily REAL DEFAULT 0,
            mtd_target REAL DEFAULT 5000000,
            mtd_pct_target REAL DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            lunch_covers INTEGER DEFAULT NULL,
            dinner_covers INTEGER DEFAULT NULL,
            FOREIGN KEY (location_id) REFERENCES locations(id),
            UNIQUE(location_id, date)
        )
        """
    )
    cols_csv = ", ".join(col_names)
    cursor.execute(
        f"INSERT INTO daily_summaries_new ({cols_csv}) SELECT {cols_csv} FROM daily_summaries"
    )
    cursor.execute("DROP TABLE daily_summaries")
    cursor.execute("ALTER TABLE daily_summaries_new RENAME TO daily_summaries")
    cursor.execute(
        "INSERT OR REPLACE INTO app_meta (k, v) VALUES (?, ?)",
        ("ds_composite_unique", "1"),
    )


def ensure_default_locations():
    """Ensure Boteco - Indiqube and Boteco - Bagmane exist (adds missing rows only)."""
    conn = get_connection()
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
    conn.close()


def create_admin_user(username: str, password: str):
    """Create admin user if not exists."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
    if cursor.fetchone() is None:
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        cursor.execute(
            """
            INSERT INTO users (username, password_hash, role)
            VALUES (?, ?, 'admin')
        """,
            (username, password_hash),
        )
        conn.commit()

    conn.close()


def verify_user(username: str, password: str) -> Optional[Dict]:
    """Verify user credentials."""
    conn = get_connection()
    cursor = conn.cursor()

    password_hash = hashlib.sha256(password.encode()).hexdigest()
    cursor.execute(
        """
        SELECT u.*, l.name as location_name
        FROM users u
        LEFT JOIN locations l ON u.location_id = l.id
        WHERE u.username = ? AND u.password_hash = ?
    """,
        (username, password_hash),
    )

    row = cursor.fetchone()
    conn.close()

    if row:
        return dict(row)
    return None


def get_all_locations() -> List[Dict]:
    """Get all locations."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM locations ORDER BY name")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def save_daily_summary(location_id: int, data: Dict) -> int:
    """Save or update daily summary."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT id FROM daily_summaries WHERE location_id = ? AND date = ?",
        (location_id, data["date"]),
    )
    existing = cursor.fetchone()

    if existing:
        summary_id = existing["id"]
        # Update existing record
        cursor.execute(
            """
            UPDATE daily_summaries SET
                covers = ?, turns = ?, gross_total = ?, net_total = ?,
                cash_sales = ?, card_sales = ?, gpay_sales = ?, zomato_sales = ?,
                other_sales = ?, service_charge = ?, cgst = ?, sgst = ?,
                discount = ?, complimentary = ?, apc = ?, target = ?,
                pct_target = ?, mtd_total_covers = ?, mtd_net_sales = ?,
                mtd_discount = ?, mtd_avg_daily = ?, mtd_target = ?, mtd_pct_target = ?,
                lunch_covers = ?, dinner_covers = ?
            WHERE id = ?
        """,
            (
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
                summary_id,
            ),
        )
    else:
        # Insert new record
        cursor.execute(
            """
            INSERT INTO daily_summaries (
                location_id, date, covers, turns, gross_total, net_total,
                cash_sales, card_sales, gpay_sales, zomato_sales, other_sales,
                service_charge, cgst, sgst, discount, complimentary, apc,
                target, pct_target, mtd_total_covers, mtd_net_sales,
                mtd_discount, mtd_avg_daily, mtd_target, mtd_pct_target,
                lunch_covers, dinner_covers
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            ),
        )
        cursor.execute("SELECT last_insert_rowid()")
        summary_id = cursor.fetchone()[0]

    # Save category sales
    if "categories" in data:
        cursor.execute("DELETE FROM category_sales WHERE summary_id = ?", (summary_id,))
        for cat in data["categories"]:
            cursor.execute(
                """
                INSERT INTO category_sales (summary_id, category, qty, amount)
                VALUES (?, ?, ?, ?)
            """,
                (summary_id, cat["category"], cat.get("qty", 0), cat.get("amount", 0)),
            )

    # Save service sales
    if "services" in data:
        cursor.execute("DELETE FROM service_sales WHERE summary_id = ?", (summary_id,))
        for svc in data["services"]:
            cursor.execute(
                """
                INSERT INTO service_sales (summary_id, service_type, amount)
                VALUES (?, ?, ?)
            """,
                (summary_id, svc["type"], svc.get("amount", 0)),
            )

    conn.commit()
    conn.close()
    return summary_id


def peek_daily_net_sales(location_id: int, date: str) -> Optional[float]:
    """Return saved net_total for a day if a row exists (lightweight; no categories)."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT net_total FROM daily_summaries
        WHERE location_id = ? AND date = ?
        """,
        (location_id, date),
    )
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    return float(row["net_total"] or 0)


def delete_daily_summary_for_location_date(location_id: int, date: str) -> bool:
    """Remove one day's summary and its category/service rows. Leaves upload_history for audit."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id FROM daily_summaries WHERE location_id = ? AND date = ?",
        (location_id, date),
    )
    row = cursor.fetchone()
    if not row:
        conn.close()
        return False
    summary_id = row["id"]
    cursor.execute("DELETE FROM category_sales WHERE summary_id = ?", (summary_id,))
    cursor.execute("DELETE FROM service_sales WHERE summary_id = ?", (summary_id,))
    cursor.execute("DELETE FROM daily_summaries WHERE id = ?", (summary_id,))
    conn.commit()
    conn.close()
    return True


def get_daily_summary(location_id: int, date: str) -> Optional[Dict]:
    """Get daily summary for a specific date."""
    conn = get_connection()
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
        # Get categories
        cursor.execute(
            "SELECT * FROM category_sales WHERE summary_id = ?", (summary["id"],)
        )
        summary["categories"] = [dict(r) for r in cursor.fetchall()]
        # Get services
        cursor.execute(
            "SELECT * FROM service_sales WHERE summary_id = ?", (summary["id"],)
        )
        summary["services"] = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return summary

    conn.close()
    return None


def get_summaries_for_month(location_id: int, year: int, month: int) -> List[Dict]:
    """Get all summaries for a specific month."""
    conn = get_connection()
    cursor = conn.cursor()

    start_date = f"{year}-{month:02d}-01"
    if month == 12:
        end_date = f"{year + 1}-01-01"
    else:
        end_date = f"{year}-{month + 1:02d}-01"

    cursor.execute(
        """
        SELECT * FROM daily_summaries 
        WHERE location_id = ? AND date >= ? AND date < ?
        ORDER BY date
    """,
        (location_id, start_date, end_date),
    )

    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_category_mtd_totals(
    location_id: int, year: int, month: int
) -> Dict[str, float]:
    """Sum category sales amounts for calendar month (all days in month)."""
    conn = get_connection()
    cursor = conn.cursor()
    start_date = f"{year}-{month:02d}-01"
    if month == 12:
        end_date = f"{year + 1}-01-01"
    else:
        end_date = f"{year}-{month + 1:02d}-01"
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
    conn.close()
    return {row["category"]: float(row["total"] or 0) for row in rows}


def get_service_mtd_totals(location_id: int, year: int, month: int) -> Dict[str, float]:
    """Sum service_sales amounts for calendar month."""
    conn = get_connection()
    cursor = conn.cursor()
    start_date = f"{year}-{month:02d}-01"
    if month == 12:
        end_date = f"{year + 1}-01-01"
    else:
        end_date = f"{year}-{month + 1:02d}-01"
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
    conn.close()
    return {row["service_type"]: float(row["total"] or 0) for row in rows}


def get_summaries_for_date_range(
    location_id: int, start_date: str, end_date: str
) -> List[Dict]:
    """Get summaries for a date range."""
    conn = get_connection()
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
    conn.close()
    return [dict(row) for row in rows]


def get_summaries_for_date_range_multi(
    location_ids: List[int], start_date: str, end_date: str
) -> List[Dict]:
    """All summaries in range for multiple locations (not merged by date)."""
    if not location_ids:
        return []
    conn = get_connection()
    cursor = conn.cursor()
    placeholders = ",".join("?" * len(location_ids))
    cursor.execute(
        f"""
        SELECT * FROM daily_summaries
        WHERE location_id IN ({placeholders}) AND date >= ? AND date <= ?
        ORDER BY date, location_id
        """,
        (*location_ids, start_date, end_date),
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_category_mtd_totals_multi(
    location_ids: List[int], year: int, month: int
) -> Dict[str, float]:
    if not location_ids:
        return {}
    conn = get_connection()
    cursor = conn.cursor()
    start_date = f"{year}-{month:02d}-01"
    if month == 12:
        end_date = f"{year + 1}-01-01"
    else:
        end_date = f"{year}-{month + 1:02d}-01"
    placeholders = ",".join("?" * len(location_ids))
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
    conn.close()
    return {row["category"]: float(row["total"] or 0) for row in rows}


def get_service_mtd_totals_multi(
    location_ids: List[int], year: int, month: int
) -> Dict[str, float]:
    if not location_ids:
        return {}
    conn = get_connection()
    cursor = conn.cursor()
    start_date = f"{year}-{month:02d}-01"
    if month == 12:
        end_date = f"{year + 1}-01-01"
    else:
        end_date = f"{year}-{month + 1:02d}-01"
    placeholders = ",".join("?" * len(location_ids))
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
    conn.close()
    return {row["service_type"]: float(row["total"] or 0) for row in rows}


def update_daily_summary_covers_only(
    location_id: int,
    date: str,
    covers: int,
    lunch_covers: Optional[int] = None,
    dinner_covers: Optional[int] = None,
) -> bool:
    """Update covers fields on an existing row; recompute apc/turns requires caller."""
    conn = get_connection()
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
        conn.close()
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
    conn.close()
    return True


def get_location_settings(location_id: int) -> Optional[Dict]:
    """Get location settings."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM locations WHERE id = ?", (location_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def update_location_settings(location_id: int, settings: Dict):
    """Update location settings."""
    conn = get_connection()
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
        vals.append(location_id)
        cursor.execute(
            f"UPDATE locations SET {', '.join(updates)} WHERE id = ?",
            vals,
        )
    conn.commit()
    conn.close()


def get_upload_history(location_id: int, limit: int = 50) -> List[Dict]:
    """Get upload history."""
    conn = get_connection()
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
    conn.close()
    return [dict(row) for row in rows]


def save_upload_record(
    location_id: int, date: str, filename: str, file_type: str, uploaded_by: str
):
    """Save upload record."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO upload_history (location_id, date, filename, file_type, uploaded_by)
        VALUES (?, ?, ?, ?, ?)
    """,
        (location_id, date, filename, file_type, uploaded_by),
    )
    conn.commit()
    conn.close()


def get_category_sales_for_date_range(
    location_ids: List[int], start_date: str, end_date: str
) -> List[Dict]:
    """
    Aggregate category sales across a date range for one or more locations.
    Returns list of {category, amount, qty} sorted by amount descending.
    """
    if not location_ids:
        return []
    placeholders = ",".join("?" * len(location_ids))
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        f"""
        SELECT cs.category,
               SUM(cs.amount) AS amount,
               SUM(cs.qty)    AS qty
        FROM category_sales cs
        JOIN daily_summaries ds ON cs.summary_id = ds.id
        WHERE ds.location_id IN ({placeholders})
          AND ds.date BETWEEN ? AND ?
        GROUP BY cs.category
        ORDER BY amount DESC
        """,
        (*location_ids, start_date, end_date),
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_service_sales_for_date_range(
    location_ids: List[int], start_date: str, end_date: str
) -> List[Dict]:
    """
    Aggregate service/meal-period sales across a date range.
    Returns list of {service_type, amount} (e.g. Breakfast, Lunch, Dinner).
    """
    if not location_ids:
        return []
    placeholders = ",".join("?" * len(location_ids))
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        f"""
        SELECT ss.service_type,
               SUM(ss.amount) AS amount
        FROM service_sales ss
        JOIN daily_summaries ds ON ss.summary_id = ds.id
        WHERE ds.location_id IN ({placeholders})
          AND ds.date BETWEEN ? AND ?
        GROUP BY ss.service_type
        ORDER BY amount DESC
        """,
        (*location_ids, start_date, end_date),
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_daily_service_sales_for_date_range(
    location_ids: List[int], start_date: str, end_date: str
) -> List[Dict]:
    """
    Per-day service/meal-period sales for stacked bar charts.
    Returns list of {date, service_type, amount} ordered by date then service_type.
    """
    if not location_ids:
        return []
    placeholders = ",".join("?" * len(location_ids))
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        f"""
        SELECT ds.date,
               ss.service_type,
               SUM(ss.amount) AS amount
        FROM service_sales ss
        JOIN daily_summaries ds ON ss.summary_id = ds.id
        WHERE ds.location_id IN ({placeholders})
          AND ds.date BETWEEN ? AND ?
        GROUP BY ds.date, ss.service_type
        ORDER BY ds.date, ss.service_type
        """,
        (*location_ids, start_date, end_date),
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


# Initialize database on module import
init_database()
ensure_default_locations()
