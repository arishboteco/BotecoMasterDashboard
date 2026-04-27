import os
from pathlib import Path


def _load_local_env(env_path: os.PathLike[str] | str | None = None) -> bool:
    """Load a local .env file without overriding real environment variables."""
    path = Path(env_path) if env_path is not None else Path(__file__).with_name(".env")
    if not path.exists():
        return False

    try:
        from dotenv import load_dotenv
    except ImportError:
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            if not key or key in os.environ:
                continue
            value = value.strip().strip('"').strip("'")
            os.environ[key] = value
        return True

    return bool(load_dotenv(dotenv_path=path, override=False))


_load_local_env()

# Boteco Dashboard Configuration

# Default Settings
MONTHLY_TARGET = 5_000_000
# DAILY_TARGET removed — daily targets are now date-aware.
# Use utils.compute_daily_target(monthly_target, year, month) instead.
SERVICE_CHARGE_RATE = 0.10
GST_RATE = 0.025

# Database
DATABASE_PATH = "data/boteco.db"

# Supabase (when using cloud database)
# Credentials must be set via environment variables — no hardcoded fallbacks.
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")

# App Settings
APP_NAME = "Boteco Dashboard"
APP_ICON = None
MIN_PASSWORD_LENGTH = 5
MAX_LOGIN_ATTEMPTS = 5
LOGIN_LOCKOUT_MINUTES = 15

# Report Settings
CURRENCY_SYMBOL = "₹"
DATE_FORMAT = "%d-%b-%Y"
CURRENCY_FORMAT = "₹{:,.0f}"

# WhatsApp Report Settings
WHATSAPP_TEMPLATE = """
{location_name}
End of Day Report
{date}

SALES SUMMARY
* Gross Total: {gross_total}
* Net Total: {net_total}
* Covers: {covers} | Turns: {turns}
* APC: {apc}

PAYMENT BREAKDOWN
* Cash: {cash_sales}
* GPay: {gpay_sales}
* Zomato: {zomato_sales}
* Card: {card_sales}

VS TARGET
* Target: {target}
* Achievement: {pct_target}%
Status: {status_text}

CATEGORY MIX
{category_breakdown}

MTD SUMMARY
* Total Covers: {mtd_covers}
* Net Sales: {mtd_sales}
* Avg Daily: {avg_daily}
"""

# File Upload Settings
ALLOWED_EXTENSIONS = ["xlsx", "xls", "csv"]
MAX_FILE_SIZE_MB = 10

# Legacy: was used by All Restaurant Sales parser (removed). Kept for any future multi-outlet tooling.
DEFAULT_RESTAURANT_FILTER = "Boteco"

# Map CSV "Restaurant" column value → DB location name.
# Used to auto-detect import location from Dynamic Report CSV files.
RESTAURANT_NAME_MAP: dict[str, str] = {
    "Boteco": "Boteco - Indiqube",
    "Boteco - Indiqube": "Boteco - Indiqube",
    "Boteco - Bagmane": "Boteco - Bagmane",
}
