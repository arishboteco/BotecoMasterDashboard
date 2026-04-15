import os

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
MIN_PASSWORD_LENGTH = 10
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
