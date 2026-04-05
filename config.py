# Boteco Dashboard Configuration

# Default Settings
MONTHLY_TARGET = 5_000_000
DAILY_TARGET = MONTHLY_TARGET / 30
SERVICE_CHARGE_RATE = 0.10
GST_RATE = 0.025

# Database
DATABASE_PATH = "data/boteco.db"

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
