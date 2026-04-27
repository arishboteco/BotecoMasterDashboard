import hashlib
import os
import sqlite3
from contextlib import contextmanager
from typing import Any, Dict, List, Optional, Tuple

try:
    import bcrypt
except ImportError:
    bcrypt = None
import config
from boteco_logger import get_logger
from db.category_rows import CATEGORY_ROW_PREFIX
from db.table_names import SQLITE_CATEGORY_SALES

logger = get_logger(__name__)

DB_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_PATH = os.path.join(DB_DIR, config.DATABASE_PATH)

os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)

# ---------------------------------------------------------------------------
# View SQL constants (shared between init_database and migration functions)
# ---------------------------------------------------------------------------
CATEGORY_SALES_VIEW_SQL = """
    CREATE VIEW IF NOT EXISTS category_sales_view AS
    SELECT
        ds.id AS summary_id,
        COALESCE(NULLIF(i.category, ''), 'Uncategorized') AS category,
        SUM(i.qty) AS qty,
        SUM(i.amount) AS amount
    FROM daily_summaries ds
    LEFT JOIN item_sales i ON i.summary_id = ds.id
    GROUP BY ds.id, COALESCE(NULLIF(i.category, ''), 'Uncategorized')
"""

SUPER_CATEGORY_SALES_VIEW_SQL = """
    CREATE VIEW IF NOT EXISTS super_category_sales_view AS
    SELECT
        ds.id AS summary_id,
        CASE
            WHEN LOWER(COALESCE(NULLIF(i.category, ''), 'Uncategorized') || '') IN (
                'beer', 'wine', 'spirits', 'cocktails', 'whisky', 'rum', 'vodka', 'gin', 'brandy'
            ) THEN 'Beverages'
            WHEN LOWER(COALESCE(NULLIF(i.category, ''), 'Uncategorized') || '') IN (
                'veg starters', 'non-veg starters', 'starters', 'appetizers', 'snacks'
            ) THEN 'Starters'
            WHEN LOWER(COALESCE(NULLIF(i.category, ''), 'Uncategorized') || '') IN (
                'veg main course', 'non-veg main course', 'main course', 'biryani', 'rice', 'curry'
            ) THEN 'Main Course'
            WHEN LOWER(COALESCE(NULLIF(i.category, ''), 'Uncategorized') || '') IN (
                'desserts', 'sweets', 'ice cream'
            ) THEN 'Desserts'
            WHEN LOWER(COALESCE(NULLIF(i.category, ''), 'Uncategorized') || '') IN (
                'soft drinks', 'juices', 'mocktails', 'shakes', 'coffee', 'tea'
            ) THEN 'Beverages - Non Alcoholic'
            ELSE 'Other'
        END AS category,
        SUM(i.qty) AS qty,
        SUM(i.amount) AS amount
    FROM daily_summaries ds
    LEFT JOIN item_sales i ON i.summary_id = ds.id
    GROUP BY ds.id,
        CASE
            WHEN LOWER(COALESCE(NULLIF(i.category, ''), 'Uncategorized') || '') IN (
                'beer', 'wine', 'spirits', 'cocktails', 'whisky', 'rum', 'vodka', 'gin', 'brandy'
            ) THEN 'Beverages'
            WHEN LOWER(COALESCE(NULLIF(i.category, ''), 'Uncategorized') || '') IN (
                'veg starters', 'non-veg starters', 'starters', 'appetizers', 'snacks'
            ) THEN 'Starters'
            WHEN LOWER(COALESCE(NULLIF(i.category, ''), 'Uncategorized') || '') IN (
                'veg main course', 'non-veg main course', 'main course', 'biryani', 'rice', 'curry'
            ) THEN 'Main Course'
            WHEN LOWER(COALESCE(NULLIF(i.category, ''), 'Uncategorized') || '') IN (
                'desserts', 'sweets', 'ice cream'
            ) THEN 'Desserts'
            WHEN LOWER(COALESCE(NULLIF(i.category, ''), 'Uncategorized') || '') IN (
                'soft drinks', 'juices', 'mocktails', 'shakes', 'coffee', 'tea'
            ) THEN 'Beverages - Non Alcoholic'
            ELSE 'Other'
        END
"""


# Secure password hashing using bcrypt (fallback to salted SHA-256 if bcrypt unavailable)
def _hash_password(password: str) -> str:
    """Hash password using bcrypt with fallback to salted SHA-256."""
    if bcrypt:
        # bcrypt automatically handles salting
        return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")
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


def _hash_session_token(token: str) -> str:
    """Hash session token before persistence."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def get_connection():
    """Get database connection with row factory."""
    conn = sqlite3.connect(DATABASE_PATH, timeout=10.0)
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


# Supabase client (lazy initialization)
_supabase_client = None
_supabase_admin_client = None
_use_supabase_override: bool | None = None


def _create_supabase_client():
    """Create a fresh Supabase client instance. Returns None if not configured.

    Streamlit runs server-side, so prefer the service-role key when present to
    avoid RLS filtering operational dashboard reads to empty results.
    """
    if not config.SUPABASE_URL or not config.SUPABASE_KEY:
        return None
    try:
        from supabase import create_client

        key = config.SUPABASE_SERVICE_KEY or config.SUPABASE_KEY
        return create_client(config.SUPABASE_URL, key)
    except ImportError:
        logger.warning("supabase package not installed")
        return None
    except Exception as e:
        logger.error("Failed to create Supabase client: %s", e)
        return None


def get_supabase_client():
    """Get or create Supabase client for server-side app operations.

    Lazily initialises on first call. Use reset_supabase_client() to force
    re-creation after a connection failure.
    """
    global _supabase_client
    if _supabase_client is None:
        _supabase_client = _create_supabase_client()
    return _supabase_client


def reset_supabase_client() -> None:
    """Force re-creation of the Supabase client on the next access.

    Call this after catching a connection error so that the next
    database operation gets a fresh client instead of a stale one.
    """
    global _supabase_client
    _supabase_client = None
    logger.info("Supabase client reset — will reconnect on next access")


def get_supabase_admin_client():
    """Get or create Supabase client with service role key (bypasses RLS).

    Requires SUPABASE_SERVICE_KEY env variable to be set.
    Returns None if not configured.
    """
    global _supabase_admin_client
    if not config.SUPABASE_SERVICE_KEY:
        return None
    if _supabase_admin_client is None:
        try:
            from supabase import create_client

            _supabase_admin_client = create_client(config.SUPABASE_URL, config.SUPABASE_SERVICE_KEY)
        except ImportError:
            logger.warning("supabase package not installed")
            return None
    return _supabase_admin_client


def use_supabase() -> bool:
    """Check if Supabase is configured and available."""
    if _use_supabase_override is not None:
        return _use_supabase_override
    if not config.SUPABASE_KEY:
        logger.debug("Supabase not configured — using SQLite")
        return False
    return bool(get_supabase_client())


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

    # User sessions for persistent login (cookie-based)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_sessions (
            token      TEXT PRIMARY KEY,
            user_id    INTEGER NOT NULL,
            expires_at DATETIME NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_user_sessions_expires
        ON user_sessions(expires_at)
    """)

    # Failed login tracking for temporary lockouts
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS auth_login_attempts (
            username TEXT PRIMARY KEY,
            failed_count INTEGER NOT NULL DEFAULT 0,
            locked_until DATETIME,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_auth_login_attempts_locked_until
        ON auth_login_attempts(locked_until)
        """
    )

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

    # Category totals table (new SQLite-native storage path; synthetic item rows remain supported).
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS category_sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            summary_id INTEGER NOT NULL,
            category_name TEXT NOT NULL,
            qty INTEGER DEFAULT 0,
            net_amount REAL DEFAULT 0,
            source TEXT DEFAULT 'direct',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (summary_id) REFERENCES daily_summaries(id),
            UNIQUE(summary_id, category_name)
        )
        """
    )

    # Create views for category sales derived from item_sales
    cursor.execute(CATEGORY_SALES_VIEW_SQL)
    cursor.execute(SUPER_CATEGORY_SALES_VIEW_SQL)

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
            category TEXT DEFAULT '',
            qty INTEGER DEFAULT 0,
            amount REAL DEFAULT 0,
            FOREIGN KEY (summary_id) REFERENCES daily_summaries(id)
        )
    """)

    # Migrations
    cursor.execute("PRAGMA table_info(daily_summaries)")
    _ds_cols = {row[1] for row in cursor.fetchall()}
    for _col, _typ in (
        ("lunch_covers", "INTEGER"),
        ("dinner_covers", "INTEGER"),
        ("order_count", "INTEGER"),
    ):
        if _col not in _ds_cols:
            cursor.execute(f"ALTER TABLE daily_summaries ADD COLUMN {_col} {_typ} DEFAULT NULL")

    cursor.execute("PRAGMA table_info(item_sales)")
    _is_cols = {row[1] for row in cursor.fetchall()}
    if "category" not in _is_cols:
        cursor.execute("ALTER TABLE item_sales ADD COLUMN category TEXT DEFAULT ''")

    cursor.execute("PRAGMA table_info(locations)")
    _loc_cols = {row[1] for row in cursor.fetchall()}
    if "seat_count" not in _loc_cols:
        cursor.execute("ALTER TABLE locations ADD COLUMN seat_count INTEGER DEFAULT NULL")

    _migrate_daily_summaries_composite_unique(cursor)

    # Query-performance indexes for reporting and analytics workloads.
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_daily_summaries_location_date
        ON daily_summaries(location_id, date)
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_daily_summaries_date
        ON daily_summaries(date)
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_daily_summaries_date_location
        ON daily_summaries(date, location_id)
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_upload_history_location_uploaded_at
        ON upload_history(location_id, uploaded_at)
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_service_sales_summary_id
        ON service_sales(summary_id)
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_item_sales_summary_id
        ON item_sales(summary_id)
        """
    )
    cursor.execute(
        f"""
        CREATE INDEX IF NOT EXISTS idx_{SQLITE_CATEGORY_SALES}_summary_id
        ON {SQLITE_CATEGORY_SALES}(summary_id)
        """
    )

    conn.commit()
    conn.close()


def migrate_category_sales_from_synthetic_rows() -> Dict[str, int]:
    """Backfill SQLite category_sales from synthetic item_sales rows.

    This is intentionally opt-in and idempotent: it inserts only missing
    (summary_id, category_name) rows and does not modify existing rows.
    """
    if use_supabase():
        return {"inserted": 0, "skipped_existing": 0}

    with db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT i.summary_id, i.category, i.qty, i.amount
            FROM item_sales i
            INNER JOIN daily_summaries ds ON ds.id = i.summary_id
            WHERE i.item_name LIKE ?
            ORDER BY i.summary_id, i.category
            """,
            (f"{CATEGORY_ROW_PREFIX}%",),
        )
        rows = cursor.fetchall()

        inserted = 0
        skipped_existing = 0
        for row in rows:
            category_name = str(row["category"] or "").strip()
            if not category_name:
                continue
            cursor.execute(
                f"""
                INSERT OR IGNORE INTO {SQLITE_CATEGORY_SALES}
                (summary_id, category_name, qty, net_amount, source)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    int(row["summary_id"]),
                    category_name,
                    int(row["qty"] or 0),
                    float(row["amount"] or 0.0),
                    "synthetic_backfill",
                ),
            )
            if cursor.rowcount:
                inserted += 1
            else:
                skipped_existing += 1

        conn.commit()
    return {"inserted": inserted, "skipped_existing": skipped_existing}


def _migrate_supabase_schema() -> None:
    """Verify Supabase schema integrity and warn about missing columns/views.

    This is a read-only check — schema fixes must be applied manually in the
    Supabase SQL editor since the execute_sql RPC is not available.
    """
    if not use_supabase():
        return

    supabase = get_supabase_admin_client()
    if supabase is None:
        logger.warning(
            "Supabase admin client unavailable — skipping schema checks. "
            "Set SUPABASE_SERVICE_KEY env variable for admin-level access."
        )
        return

    for view_name in ("category_sales", "super_category_sales"):
        try:
            supabase.table(view_name).select("id").limit(1).execute()
        except Exception:
            logger.warning(
                "Supabase view '%s' is missing. Run the Supabase migration that creates this view.",
                view_name,
            )


def _migrate_daily_summaries_composite_unique(cursor) -> None:
    """Replace legacy UNIQUE(date) with UNIQUE(location_id, date)."""
    cursor.execute("SELECT v FROM app_meta WHERE k = ?", ("ds_composite_unique",))
    if cursor.fetchone():
        return
    cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='daily_summaries'")
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
    # Drop views that depend on daily_summaries before dropping the table
    cursor.execute("DROP VIEW IF EXISTS category_sales_view")
    cursor.execute("DROP VIEW IF EXISTS super_category_sales_view")
    cursor.execute("DROP TABLE daily_summaries")
    cursor.execute("ALTER TABLE daily_summaries_new RENAME TO daily_summaries")
    # Recreate the views pointing at the renamed table
    cursor.execute(CATEGORY_SALES_VIEW_SQL)
    cursor.execute(SUPER_CATEGORY_SALES_VIEW_SQL)
    cursor.execute(
        "INSERT OR REPLACE INTO app_meta (k, v) VALUES (?, ?)",
        ("ds_composite_unique", "1"),
    )


def ensure_default_locations():
    """Ensure Boteco - Indiqube and Boteco - Bagmane exist (adds missing rows only)."""
    from database_writes import ensure_default_locations as _impl

    _impl()


def create_admin_user(username: str, password: str) -> None:
    """Create the default admin user when missing."""
    from database_auth import create_admin_user as _impl

    _impl(username, password)


def verify_user(username: str, password: str) -> Optional[Dict]:
    """Verify user credentials using secure password verification."""
    from database_auth import verify_user as _impl

    return _impl(username, password)


def get_all_locations() -> List[Dict]:
    """Get all locations."""
    from database_reads import get_all_locations as _impl

    return _impl()


def save_daily_summary(location_id: int, data: Dict) -> int:
    """Save or update daily summary using INSERT OR REPLACE for atomic upsert."""
    from database_writes import save_daily_summary as _impl

    return _impl(location_id, data)


def peek_daily_net_sales(location_id: int, date: str) -> Optional[float]:
    """Return saved net_total for a day if a row exists (lightweight; no categories)."""
    from database_reads import peek_daily_net_sales as _impl

    return _impl(location_id, date)


def delete_daily_summary_for_location_date(location_id: int, date: str) -> bool:
    """Remove one day's summary and its child rows. Leaves upload_history for audit."""
    from database_writes import delete_daily_summary_for_location_date as _impl

    return _impl(location_id, date)


# ── User management ───────────────────────────────────────────────────────────


def get_all_users() -> List[Dict]:
    """Return all users (password_hash excluded)."""
    from database_auth import get_all_users as _impl

    return _impl()


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
    from database_auth import create_user as _impl

    return _impl(username, password, role, location_id, email)


def update_user(
    user_id: int,
    role: Optional[str] = None,
    location_id: Optional[int] = None,
    email: Optional[str] = None,
    new_password: Optional[str] = None,
) -> Tuple[bool, str]:
    """Update role, location, email, and/or password for an existing user."""
    from database_auth import update_user as _impl

    return _impl(user_id, role, location_id, email, new_password)


def delete_user(user_id: int, current_username: str) -> Tuple[bool, str]:
    """Delete a user. Prevents deleting yourself."""
    from database_auth import delete_user as _impl

    return _impl(user_id, current_username)


# ── Location management ───────────────────────────────────────────────────────


def create_location(
    name: str,
    monthly_target: float = 5_000_000,
    seat_count: Optional[int] = None,
) -> Tuple[bool, str]:
    """Add a new outlet location."""
    from database_writes import create_location as _impl

    return _impl(name, monthly_target, seat_count)


def delete_location(location_id: int) -> Tuple[bool, str]:
    """
    Delete a location. Refuses if it has any saved daily summaries (data safety).
    """
    from database_writes import delete_location as _impl

    return _impl(location_id)


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
    from database_reads import get_all_summaries_for_export as _impl

    return _impl(location_ids, start_date, end_date)


def get_daily_summary(location_id: int, date: str) -> Optional[Dict]:
    """Get daily summary for a specific date."""
    from database_reads import get_daily_summary as _impl

    return _impl(location_id, date)


def get_summaries_for_month(location_id: int, year: int, month: int) -> List[Dict]:
    """Get all summaries for a specific month."""
    from database_reads import get_summaries_for_month as _impl

    return _impl(location_id, year, month)


def get_category_mtd_totals(location_ids: List[int], year: int, month: int) -> List[Dict]:
    """Return category rows from month start onward for the given locations."""
    from database_reads import get_category_mtd_totals as _impl

    return _impl(location_ids, year, month)


def get_service_mtd_totals(location_id: int, year: int, month: int) -> Dict[str, float]:
    """Legacy facade: delegates to database_reads.get_service_mtd_totals()."""
    from database_reads import get_service_mtd_totals as _impl

    return _impl(location_id, year, month)


def get_mtd_totals_multi(location_ids: List[int], year: int, month: int) -> Dict[str, float]:
    """Fetch aggregate MTD summary totals across multiple locations."""
    from database_reads import get_mtd_totals_multi as _impl

    return _impl(location_ids, year, month)


def get_summaries_for_month_multi(location_ids: List[int], year: int, month: int) -> List[Dict]:
    """Get all summaries for a specific month across multiple locations."""
    from database_reads import get_summaries_for_month_multi as _impl

    return _impl(location_ids, year, month)


def get_summaries_for_date_range(location_id: int, start_date: str, end_date: str) -> List[Dict]:
    """Get summaries for a date range."""
    from database_reads import get_summaries_for_date_range as _impl

    return _impl(location_id, start_date, end_date)


def get_summaries_for_date_range_multi(
    location_ids: List[int], start_date: str, end_date: str
) -> List[Dict]:
    """All summaries in range for multiple locations (not merged by date)."""
    from database_reads import get_summaries_for_date_range_multi as _impl

    return _impl(location_ids, start_date, end_date)


def get_most_recent_date_with_data(location_ids: List[int]) -> Optional[str]:
    """Get most recent saved summary date across one or more locations."""
    from database_reads import get_most_recent_date_with_data as _impl

    return _impl(location_ids)


def get_monthly_footfall_multi(
    location_ids: List[int], start_date: str, end_date: str
) -> List[Dict[str, Any]]:
    """Aggregate covers by month across locations for a date range."""
    from database_analytics import get_monthly_footfall_multi as _impl

    return _impl(location_ids, start_date, end_date)


def get_weekly_footfall_multi(
    location_ids: List[int], start_date: str, end_date: str
) -> List[Dict[str, Any]]:
    """Aggregate covers by ISO week across locations for a date range."""
    from database_analytics import get_weekly_footfall_multi as _impl

    return _impl(location_ids, start_date, end_date)


def get_category_mtd_totals_multi(
    location_ids: List[int], year: int, month: int
) -> Dict[str, float]:
    """Legacy facade: delegates to database_analytics.get_category_mtd_totals_multi()."""
    from database_analytics import get_category_mtd_totals_multi as _impl

    return _impl(location_ids, year, month)


def get_service_mtd_totals_multi(
    location_ids: List[int], year: int, month: int
) -> Dict[str, float]:
    """Legacy facade: delegates to database_analytics.get_service_mtd_totals_multi()."""
    from database_analytics import get_service_mtd_totals_multi as _impl

    return _impl(location_ids, year, month)


def update_daily_summary_covers_only(
    location_id: int,
    date: str,
    covers: int,
    lunch_covers: Optional[int] = None,
    dinner_covers: Optional[int] = None,
) -> bool:
    """Update covers fields on an existing row; recompute apc/turns requires caller."""
    from database_writes import update_daily_summary_covers_only as _impl

    return _impl(location_id, date, covers, lunch_covers, dinner_covers)


def get_location_settings(location_id: int) -> Optional[Dict]:
    """Get location settings."""
    from database_reads import get_location_settings as _impl

    return _impl(location_id)


def update_location_settings(location_id: int, settings: Dict[str, Any]) -> None:
    """Update location settings."""
    from database_writes import update_location_settings as _impl

    _impl(location_id, settings)


def get_upload_history(location_id: int, limit: int = 50) -> List[Dict]:
    """Get upload history."""
    from database_reads import get_upload_history as _impl

    return _impl(location_id, limit)


def get_recent_summaries(location_id: int, weeks: int = 8) -> List[Dict]:
    """Fetch recent daily summaries for weekday mix analysis."""
    from database_reads import get_recent_summaries as _impl

    return _impl(location_id, weeks)


def save_upload_record(
    location_id: int, date: str, filename: str, file_type: str, uploaded_by: str
) -> None:
    """Save upload record."""
    from database_writes import save_upload_record as _impl

    _impl(location_id, date, filename, file_type, uploaded_by)


def backfill_weekday_weighted_targets() -> Tuple[int, int]:
    """One-time backfill: recompute all existing daily_summaries target values.

    Uses per-location weekday mix to produce day-specific targets instead of uniform.
    Returns (updated_count, locations_processed). Idempotent — only runs once.
    """
    from database_writes import backfill_weekday_weighted_targets as _impl

    return _impl()


def get_top_items_for_date_range(
    location_ids: List[int], start_date: str, end_date: str, limit: int = 20
) -> List[Dict]:
    """Top-selling menu items across a date range for one or more locations."""
    from database_analytics import get_top_items_for_date_range as _impl

    return _impl(location_ids, start_date, end_date, limit)


def get_category_sales_for_date_range(
    location_ids: List[int], start_date: str, end_date: str
) -> List[Dict]:
    """Aggregate category sales across a date range for one or more locations."""
    from database_analytics import get_category_sales_for_date_range as _impl

    return _impl(location_ids, start_date, end_date)


def get_service_sales_for_date_range(
    location_ids: List[int], start_date: str, end_date: str
) -> List[Dict]:
    """Aggregate service/meal-period sales across a date range."""
    from database_analytics import get_service_sales_for_date_range as _impl

    return _impl(location_ids, start_date, end_date)


def get_daily_service_sales_for_date_range(
    location_ids: List[int], start_date: str, end_date: str
) -> List[Dict]:
    """Per-day service/meal-period sales for stacked bar charts."""
    from database_analytics import get_daily_service_sales_for_date_range as _impl

    return _impl(location_ids, start_date, end_date)


def get_super_category_mtd_totals(location_id: int, year: int, month: int) -> Dict[str, float]:
    """Sum super-category sales amounts for calendar month."""
    from database_analytics import get_super_category_mtd_totals as _impl

    return _impl(location_id, year, month)


def get_super_category_mtd_totals_multi(
    location_ids: List[int], year: int, month: int
) -> Dict[str, float]:
    """Sum super-category sales across multiple locations for calendar month."""
    from database_analytics import get_super_category_mtd_totals_multi as _impl

    return _impl(location_ids, year, month)


def get_super_category_sales_for_date_range(
    location_ids: List[int], start_date: str, end_date: str
) -> List[Dict]:
    """Aggregate super-category sales across a date range."""
    from database_analytics import get_super_category_sales_for_date_range as _impl

    return _impl(location_ids, start_date, end_date)


def get_item_sales_for_date_range(
    location_ids: List[int], start_date: str, end_date: str, limit: int = 30
) -> List[Dict]:
    """Top-selling menu items across a date range for one or more locations."""
    from database_analytics import get_item_sales_for_date_range as _impl

    return _impl(location_ids, start_date, end_date, limit)


def create_user_session(user_id: int, days: int = 30) -> str:
    """Generate and persist a secure session token. Returns the token string."""
    from database_auth import create_user_session as _impl

    return _impl(user_id, days)


def validate_session_token(token: str) -> Optional[Dict]:
    """Return user dict for a valid non-expired token, or None."""
    from database_auth import validate_session_token as _impl

    return _impl(token)


def delete_session_token(token: str) -> None:
    """Remove a session token on logout."""
    from database_auth import delete_session_token as _impl

    _impl(token)


def purge_expired_sessions() -> None:
    """Delete all expired sessions. Called at bootstrap."""
    from database_auth import purge_expired_sessions as _impl

    _impl()


def is_login_locked(username: str) -> Tuple[bool, int]:
    """Return whether username is temporarily login-locked and remaining minutes."""
    from database_auth import is_login_locked as _impl

    return _impl(username)


def record_failed_login(username: str) -> Tuple[bool, int]:
    """Record failed login attempt and return lock state."""
    from database_auth import record_failed_login as _impl

    return _impl(username)


def clear_failed_login(username: str) -> None:
    """Clear failed login tracking for username."""
    from database_auth import clear_failed_login as _impl

    _impl(username)


def bootstrap() -> None:
    """Initialize database and ensure default locations exist. Call explicitly from app.py."""
    logger.info("Bootstrapping database")
    init_database()
    _migrate_supabase_schema()
    ensure_default_locations()
    purge_expired_sessions()


def wipe_all_data() -> Tuple[Dict[str, int], List[str]]:
    """Delete ALL operational data (summaries, categories, services, uploads, items).

    Preserves: locations, users, location_settings tables.
    Returns tuple of ({table_name: deleted_count}, [error_messages]).

    WARNING: This is irreversible. Only call from admin UI with explicit confirmation.
    """
    from database_writes import wipe_all_data as _impl

    return _impl()


# ---------------------------------------------------------------------------
# Facade exports (authoritative import path: this module)
# ---------------------------------------------------------------------------
AUTH_EXPORTS = [
    "create_admin_user",
    "verify_user",
    "get_all_users",
    "create_user",
    "update_user",
    "delete_user",
    "create_user_session",
    "validate_session_token",
    "delete_session_token",
    "purge_expired_sessions",
    "is_login_locked",
    "record_failed_login",
    "clear_failed_login",
]

READ_EXPORTS = [
    "get_all_locations",
    "peek_daily_net_sales",
    "get_all_summaries_for_export",
    "get_daily_summary",
    "get_summaries_for_month",
    "get_category_mtd_totals",
    "get_service_mtd_totals",
    "get_summaries_for_date_range",
    "get_summaries_for_date_range_multi",
    "get_mtd_totals_multi",
    "get_summaries_for_month_multi",
    "get_most_recent_date_with_data",
    "get_location_settings",
    "get_upload_history",
    "get_recent_summaries",
    "get_category_mtd_totals_multi",
    "get_service_mtd_totals_multi",
]

WRITE_EXPORTS = [
    "ensure_default_locations",
    "save_daily_summary",
    "delete_daily_summary_for_location_date",
    "create_location",
    "delete_location",
    "migrate_category_sales_from_synthetic_rows",
    "update_daily_summary_covers_only",
    "update_location_settings",
    "save_upload_record",
    "backfill_weekday_weighted_targets",
    "wipe_all_data",
]

ANALYTICS_EXPORTS = [
    "get_monthly_footfall_multi",
    "get_weekly_footfall_multi",
    "get_top_items_for_date_range",
    "get_category_sales_for_date_range",
    "get_service_sales_for_date_range",
    "get_daily_service_sales_for_date_range",
    "get_super_category_mtd_totals",
    "get_super_category_mtd_totals_multi",
    "get_super_category_sales_for_date_range",
    "get_item_sales_for_date_range",
]

DELEGATED_SYMBOL_ORIGINS = {
    # auth
    "create_admin_user": "database_auth",
    "verify_user": "database_auth",
    "get_all_users": "database_auth",
    "create_user": "database_auth",
    "update_user": "database_auth",
    "delete_user": "database_auth",
    "create_user_session": "database_auth",
    "validate_session_token": "database_auth",
    "delete_session_token": "database_auth",
    "purge_expired_sessions": "database_auth",
    "is_login_locked": "database_auth",
    "record_failed_login": "database_auth",
    "clear_failed_login": "database_auth",
    # reads
    "get_all_locations": "database_reads",
    "peek_daily_net_sales": "database_reads",
    "get_all_summaries_for_export": "database_reads",
    "get_daily_summary": "database_reads",
    "get_summaries_for_month": "database_reads",
    "get_category_mtd_totals": "database_reads",
    "get_service_mtd_totals": "database_reads",
    "get_summaries_for_date_range": "database_reads",
    "get_summaries_for_date_range_multi": "database_reads",
    "get_mtd_totals_multi": "database_reads",
    "get_summaries_for_month_multi": "database_reads",
    "get_most_recent_date_with_data": "database_reads",
    "get_location_settings": "database_reads",
    "get_upload_history": "database_reads",
    "get_recent_summaries": "database_reads",
    "get_category_mtd_totals_multi": "database_reads",
    "get_service_mtd_totals_multi": "database_reads",
    # writes
    "ensure_default_locations": "database_writes",
    "save_daily_summary": "database_writes",
    "delete_daily_summary_for_location_date": "database_writes",
    "create_location": "database_writes",
    "delete_location": "database_writes",
    "update_daily_summary_covers_only": "database_writes",
    "update_location_settings": "database_writes",
    "save_upload_record": "database_writes",
    "backfill_weekday_weighted_targets": "database_writes",
    "wipe_all_data": "database_writes",
    # analytics
    "get_monthly_footfall_multi": "database_analytics",
    "get_weekly_footfall_multi": "database_analytics",
    "get_top_items_for_date_range": "database_analytics",
    "get_category_sales_for_date_range": "database_analytics",
    "get_service_sales_for_date_range": "database_analytics",
    "get_daily_service_sales_for_date_range": "database_analytics",
    "get_super_category_mtd_totals": "database_analytics",
    "get_super_category_mtd_totals_multi": "database_analytics",
    "get_super_category_sales_for_date_range": "database_analytics",
    "get_item_sales_for_date_range": "database_analytics",
}

FACADE_EXPORT_GROUPS = {
    "auth": AUTH_EXPORTS,
    "reads": READ_EXPORTS,
    "writes": WRITE_EXPORTS,
    "analytics": ANALYTICS_EXPORTS,
}

__all__ = [
    "get_connection",
    "db_connection",
    "init_database",
    "bootstrap",
    "use_supabase",
    "get_supabase_client",
    "reset_supabase_client",
    "get_supabase_admin_client",
    "AUTH_EXPORTS",
    "READ_EXPORTS",
    "WRITE_EXPORTS",
    "ANALYTICS_EXPORTS",
    "FACADE_EXPORT_GROUPS",
    "DELEGATED_SYMBOL_ORIGINS",
    *AUTH_EXPORTS,
    *READ_EXPORTS,
    *WRITE_EXPORTS,
    *ANALYTICS_EXPORTS,
]
