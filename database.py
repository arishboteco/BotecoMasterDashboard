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

    # Daily summaries table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS daily_summaries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            location_id INTEGER NOT NULL,
            date DATE NOT NULL UNIQUE,
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
            FOREIGN KEY (location_id) REFERENCES locations(id)
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

    conn.commit()
    conn.close()


def create_default_location():
    """Create default location if not exists."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM locations WHERE name = ?", ("Boteco Bangalore",))
    if cursor.fetchone() is None:
        cursor.execute(
            """
            INSERT INTO locations (name, target_monthly_sales, target_daily_sales)
            VALUES (?, ?, ?)
        """,
            ("Boteco Bangalore", config.MONTHLY_TARGET, config.DAILY_TARGET),
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
                mtd_discount = ?, mtd_avg_daily = ?, mtd_target = ?, mtd_pct_target = ?
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
                mtd_discount, mtd_avg_daily, mtd_target, mtd_pct_target
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
    cursor.execute(
        """
        UPDATE locations SET
            name = COALESCE(?, name),
            target_monthly_sales = COALESCE(?, target_monthly_sales)
        WHERE id = ?
    """,
        (settings.get("name"), settings.get("target_monthly_sales"), location_id),
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


# Initialize database on module import
init_database()
create_default_location()
