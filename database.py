import sqlite3
import hashlib
import os
from contextlib import contextmanager
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple, Generator

try:
    import bcrypt
except ImportError:
    bcrypt = None
import config
from logger import get_logger

logger = get_logger(__name__)

DB_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_PATH = os.path.join(DB_DIR, config.DATABASE_PATH)

os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)


# Secure password hashing using bcrypt (fallback to salted SHA-256 if bcrypt unavailable)
def _hash_password(password: str) -> str:
    """Hash password using bcrypt with fallback to salted SHA-256."""
    if bcrypt:
        # bcrypt automatically handles salting
        return bcrypt.hashpw(
            password.encode("utf-8"), bcrypt.gensalt(rounds=12)
        ).decode("utf-8")
    else:
        # Fallback: use SHA-256 with random salt (less secure but better than unsalted)
        salt = os.urandom(32).hex()
        salted = (salt + password).encode("utf-8")
        return f"salt:{salt}:{hashlib.sha256(salted).hexdigest()}"


def _verify_password(password: str, password_hash: str) -> bool:
    """Verify password against hash (supports both bcrypt and legacy SHA-256)."""
    if not password_hash:
        return False

    if bcrypt and password_hash.startswith("$2"):
        # bcrypt hash
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    elif password_hash.startswith("salt:"):
        # New salted SHA-256 format
        parts = password_hash.split(":")
        if len(parts) == 3:
            salt = parts[1]
            salted = (salt + password).encode("utf-8")
            return hashlib.sha256(salted).hexdigest() == parts[2]
        return False
    else:
        # Legacy unsalted SHA-256 (for backward compatibility during migration)
        return hashlib.sha256(password.encode()).hexdigest() == password_hash


def get_connection():
    """Get database connection with row factory."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def db_connection():
    """Context manager for database connections. Preferred for new code."""
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()


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

    # item_sales table — top-selling items per day
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS item_sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            summary_id INTEGER NOT NULL,
            item_name TEXT NOT NULL,
            qty INTEGER DEFAULT 0,
            amount REAL DEFAULT 0,
            FOREIGN KEY (summary_id) REFERENCES daily_summaries(id)
        )
    """)

    cursor.execute("PRAGMA table_info(daily_summaries)")
    _ds_cols = {row[1] for row in cursor.fetchall()}
    for _col, _typ in (
        ("lunch_covers", "INTEGER"),
        ("dinner_covers", "INTEGER"),
        ("order_count", "INTEGER"),
    ):
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
            order_count INTEGER DEFAULT 0,
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
        password_hash = _hash_password(password)
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
    """Verify user credentials using secure password verification."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT u.*, l.name as location_name
        FROM users u
        LEFT JOIN locations l ON u.location_id = l.id
        WHERE u.username = ?
    """,
        (username,),
    )
    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    # Verify password against stored hash
    if _verify_password(password, row["password_hash"]):
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
    logger.info(
        "Saving daily summary for location_id=%s date=%s", location_id, data.get("date")
    )
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
                lunch_covers = ?, dinner_covers = ?, order_count = ?
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
                data.get("order_count"),
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

    # Save item sales (top sellers)
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
    """Remove one day's summary and its child rows. Leaves upload_history for audit."""
    logger.info("Deleting daily summary for location_id=%s date=%s", location_id, date)
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
    cursor.execute("DELETE FROM service_sales  WHERE summary_id = ?", (summary_id,))
    cursor.execute("DELETE FROM item_sales     WHERE summary_id = ?", (summary_id,))
    cursor.execute("DELETE FROM daily_summaries WHERE id = ?", (summary_id,))
    conn.commit()
    conn.close()
    return True


# ── User management ───────────────────────────────────────────────────────────


def get_all_users() -> List[Dict]:
    """Return all users (password_hash excluded)."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT u.id, u.username, u.email, u.role, u.location_id,
               u.created_at, l.name AS location_name
        FROM users u
        LEFT JOIN locations l ON u.location_id = l.id
        ORDER BY u.username
        """
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def create_user(
    username: str,
    password: str,
    role: str = "manager",
    location_id: Optional[int] = None,
    email: str = "",
) -> Tuple[bool, str]:
    """
    Create a new user. Returns (success, message).
    Fails if username already exists or password is too short.
    """
    if len(password) < 6:
        return False, "Password must be at least 6 characters."
    if not username.strip():
        return False, "Username cannot be empty."
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE username = ?", (username.strip(),))
    if cursor.fetchone():
        conn.close()
        return False, f"Username '{username}' already exists."
    pw_hash = _hash_password(password)
    cursor.execute(
        """
        INSERT INTO users (username, password_hash, email, role, location_id)
        VALUES (?, ?, ?, ?, ?)
        """,
        (username.strip(), pw_hash, email.strip(), role, location_id),
    )
    conn.commit()
    conn.close()
    return True, f"User '{username}' created."


def update_user(
    user_id: int,
    role: Optional[str] = None,
    location_id: Optional[int] = None,
    email: Optional[str] = None,
    new_password: Optional[str] = None,
) -> Tuple[bool, str]:
    """Update role, location, email, and/or password for an existing user."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, username FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return False, "User not found."
    username = row["username"]
    if role is not None:
        cursor.execute("UPDATE users SET role = ? WHERE id = ?", (role, user_id))
    if location_id is not None:
        cursor.execute(
            "UPDATE users SET location_id = ? WHERE id = ?", (location_id, user_id)
        )
    if email is not None:
        cursor.execute("UPDATE users SET email = ? WHERE id = ?", (email, user_id))
    if new_password is not None:
        if len(new_password) < 6:
            conn.close()
            return False, "Password must be at least 6 characters."
        pw_hash = _hash_password(new_password)
        cursor.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?", (pw_hash, user_id)
        )
    conn.commit()
    conn.close()
    return True, f"User '{username}' updated."


def delete_user(user_id: int, current_username: str) -> Tuple[bool, str]:
    """Delete a user. Prevents deleting yourself."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT username FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return False, "User not found."
    if row["username"] == current_username:
        conn.close()
        return False, "You cannot delete your own account."
    uname = row["username"]
    cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    return True, f"User '{uname}' deleted."


# ── Location management ───────────────────────────────────────────────────────


def create_location(
    name: str,
    monthly_target: float = 5_000_000,
    seat_count: Optional[int] = None,
) -> Tuple[bool, str]:
    """Add a new outlet location."""
    if not name.strip():
        return False, "Location name cannot be empty."
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM locations WHERE name = ?", (name.strip(),))
    if cursor.fetchone():
        conn.close()
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
    conn.close()
    return True, f"Location '{name}' created."


def delete_location(location_id: int) -> Tuple[bool, str]:
    """
    Delete a location. Refuses if it has any saved daily summaries (data safety).
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM locations WHERE id = ?", (location_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return False, "Location not found."
    name = row["name"]
    cursor.execute(
        "SELECT COUNT(*) AS n FROM daily_summaries WHERE location_id = ?",
        (location_id,),
    )
    count = cursor.fetchone()["n"]
    if count > 0:
        conn.close()
        return (
            False,
            f"Cannot delete '{name}' — it has {count} saved day(s) of data. "
            "Remove all data first or archive the location instead.",
        )
    cursor.execute("DELETE FROM locations WHERE id = ?", (location_id,))
    conn.commit()
    conn.close()
    return True, f"Location '{name}' deleted."


# ── Data export ───────────────────────────────────────────────────────────────


def get_all_summaries_for_export(
    location_ids: Optional[List[int]] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> List[Dict]:
    """
    Return daily_summaries rows (with location name) for CSV/Excel export.
    Excludes internal IDs and MTD fields to keep the export clean.
    """
    conn = get_connection()
    cursor = conn.cursor()

    conditions = []
    params: List[Any] = []

    if location_ids:
        placeholders = ",".join("?" * len(location_ids))
        conditions.append(f"ds.location_id IN ({placeholders})")
        params.extend(location_ids)
    if start_date:
        conditions.append("ds.date >= ?")
        params.append(start_date)
    if end_date:
        conditions.append("ds.date <= ?")
        params.append(end_date)

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    cursor.execute(
        f"""
        SELECT
            l.name            AS outlet,
            ds.date,
            ds.covers,
            ds.order_count,
            ds.gross_total,
            ds.net_total,
            ds.cash_sales,
            ds.card_sales,
            ds.gpay_sales,
            ds.zomato_sales,
            ds.other_sales,
            ds.discount,
            ds.complimentary,
            ds.service_charge,
            ds.cgst,
            ds.sgst,
            ds.apc,
            ds.turns,
            ds.target,
            ds.pct_target,
            ds.lunch_covers,
            ds.dinner_covers,
            ds.mtd_net_sales,
            ds.mtd_total_covers,
            ds.mtd_avg_daily,
            ds.mtd_target,
            ds.mtd_pct_target
        FROM daily_summaries ds
        JOIN locations l ON ds.location_id = l.id
        {where}
        ORDER BY ds.date DESC, l.name
        """,
        params,
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


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


def get_monthly_footfall_multi(
    location_ids: List[int], start_date: str, end_date: str
) -> List[Dict]:
    """Aggregate covers by month across locations for a date range.

    Returns list of dicts: [{"month": "YYYY-MM", "covers": int, "total_days": int}, ...]
    Sorted by month ascending.
    """
    if not location_ids:
        return []
    conn = get_connection()
    cursor = conn.cursor()
    placeholders = ",".join("?" * len(location_ids))
    cursor.execute(
        f"""
        SELECT
            SUBSTR(date, 1, 7) AS month,
            SUM(covers) AS covers,
            COUNT(DISTINCT date) AS total_days
        FROM daily_summaries
        WHERE location_id IN ({placeholders})
          AND date >= ?
          AND date <= ?
        GROUP BY SUBSTR(date, 1, 7)
        ORDER BY month
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


def get_top_items_for_date_range(
    location_ids: List[int], start_date: str, end_date: str, limit: int = 20
) -> List[Dict]:
    """
    Top-selling menu items across a date range for one or more locations.
    Returns list of {item_name, amount, qty} sorted by amount descending.
    """
    if not location_ids:
        return []
    placeholders = ",".join("?" * len(location_ids))
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        f"""
        SELECT it.item_name,
               SUM(it.amount) AS amount,
               SUM(it.qty)    AS qty
        FROM item_sales it
        JOIN daily_summaries ds ON it.summary_id = ds.id
        WHERE ds.location_id IN ({placeholders})
          AND ds.date BETWEEN ? AND ?
        GROUP BY it.item_name
        ORDER BY amount DESC
        LIMIT ?
        """,
        (*location_ids, start_date, end_date, limit),
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


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


def bootstrap():
    """Initialize database and ensure default locations exist. Call explicitly from app.py."""
    logger.info("Bootstrapping database")
    init_database()
    ensure_default_locations()


def wipe_all_data() -> Dict[str, int]:
    """Delete ALL operational data (summaries, categories, services, uploads, items).

    Preserves: locations, users, location_settings tables.
    Returns dict of {table_name: deleted_count} for confirmation.

    WARNING: This is irreversible. Only call from admin UI with explicit confirmation.
    """
    conn = get_connection()
    cursor = conn.cursor()

    counts = {}

    # Delete in foreign-key dependency order (children first)
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
        except Exception:
            counts[table] = 0

    conn.commit()
    conn.close()

    total = sum(counts.values())
    logger.info(f"Wiped all data: {total} records deleted across {len(counts)} tables")
    return counts
