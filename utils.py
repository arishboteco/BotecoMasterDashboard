from datetime import datetime, timedelta
from typing import List, Dict, Optional
import config


def format_currency(amount: float) -> str:
    """Format amount as Indian currency string.

    Uses Indian numbering system: 1,30,235 instead of 130,235
    """
    return format_indian_currency(amount)


def format_rupee_short(amount: float) -> str:
    """Format rupee amount as short label: ₹1.3k, ₹130k, ₹1.3L, ₹15L.

    Uses 1 decimal place for clarity. For use in KPI cards and compact displays.
    """
    abs_amt = abs(amount)
    sign = "-" if amount < 0 else ""
    if abs_amt >= 1_00_000:
        lakhs = abs_amt / 1_00_000
        return f"{sign}₹{lakhs:.1f}L"
    elif abs_amt >= 1_000:
        k = abs_amt / 1_000
        return f"{sign}₹{k:.1f}k"
    else:
        return f"{sign}₹{abs_amt:.0f}"


def format_indian_number(num: float) -> str:
    """Format number using Indian numbering system (lakhs/crores).

    Example: 1234567 → 12,34,567
    """
    if num < 0:
        return f"-{format_indian_number(abs(num))}"
    s = str(int(num))
    if len(s) <= 3:
        return s
    # Last 3 digits
    result = s[-3:]
    s = s[:-3]
    # Groups of 2 from right
    while s:
        result = s[-2:] + "," + result
        s = s[:-2]
    return result


def format_indian_currency(amount: float) -> str:
    """Format amount as Indian currency with ₹ symbol and Indian numbering.

    Handles positive, negative, zero, and decimal amounts.
    Example: 1234567.50 → ₹12,34,567.50
    """
    is_negative = amount < 0
    amount = abs(amount)

    # Split into integer and decimal parts
    if isinstance(amount, float) and amount % 1 != 0:
        parts = f"{amount:.2f}".split(".")
        integer_part = parts[0]
        decimal_part = parts[1]
    else:
        integer_part = str(int(amount))
        decimal_part = None

    # Format integer part with Indian numbering
    if len(integer_part) <= 3:
        formatted_int = integer_part
    else:
        # Last 3 digits
        result = integer_part[-3:]
        s = integer_part[:-3]
        # Groups of 2 from right
        while s:
            result = s[-2:] + "," + result
            s = s[:-2]
        formatted_int = result

    # Combine with decimal part
    if decimal_part and int(decimal_part) > 0:
        formatted = f"{formatted_int}.{decimal_part}"
    else:
        formatted = formatted_int

    # Add sign and currency symbol
    if is_negative:
        return f"-₹{formatted}"
    return f"₹{formatted}"


def format_number(num: float, decimals: int = 0) -> str:
    """Format number with commas."""
    if decimals > 0:
        return f"{num:,.{decimals}f}"
    return f"{num:,.0f}"


def format_percent(value: Optional[float]) -> str:
    """Format percentage with 2 decimal places."""
    return f"{float(value or 0):.2f}%"


def format_delta(
    current: float, prior: float, is_currency: bool = True, is_percent: bool = False
) -> Optional[str]:
    """Format a delta string with sign prefix for Streamlit color parsing.

    Returns None if prior is None or zero (no comparison possible).
    Always includes sign at start of string so Streamlit parses coloring correctly.
    """
    if prior is None or prior == 0:
        return None
    g = calculate_growth(current, prior)
    change = g["change"]
    pct = g["percentage"]
    if change >= 0:
        sign = "+"
    else:
        sign = "-"
        change = abs(change)
        pct = abs(pct)
    if is_currency:
        return f"{sign}{format_currency(change)} ({sign}{format_percent(pct)})"
    elif is_percent:
        return f"{sign}{format_percent(change)}pp"
    else:
        return f"{sign}{change:,.0f} ({sign}{format_percent(pct)})"


def format_date(date_str: Optional[str], output_format: Optional[str] = None) -> str:
    """Format date string."""
    if not date_str:
        return ""

    try:
        if isinstance(date_str, str):
            dt = datetime.strptime(date_str, "%Y-%m-%d")
        else:
            dt = date_str

        if output_format:
            return dt.strftime(output_format)
        return dt.strftime(config.DATE_FORMAT)
    except Exception:
        return str(date_str)


def get_date_range(period: str) -> tuple:
    """Get date range for common periods."""
    today = datetime.now().date()

    if period == "today":
        return today, today
    elif period == "yesterday":
        yesterday = today - timedelta(days=1)
        return yesterday, yesterday
    elif period == "this_week":
        start = today - timedelta(days=today.weekday())
        return start, today
    elif period == "last_week":
        end = today - timedelta(days=today.weekday() + 1)
        start = end - timedelta(days=6)
        return start, end
    elif period == "this_month":
        start = today.replace(day=1)
        return start, today
    elif period == "last_month":
        first_this_month = today.replace(day=1)
        end = first_this_month - timedelta(days=1)
        start = end.replace(day=1)
        return start, end
    elif period == "last_7_days":
        return today - timedelta(days=6), today
    elif period == "last_30_days":
        return today - timedelta(days=29), today
    else:
        return today, today


def calculate_growth(current: float, previous: float) -> Dict:
    """Calculate growth metrics."""
    if previous == 0:
        return {
            "absolute": current,
            "change": 0,
            "percentage": 0,
            "direction": "neutral",
        }

    change = current - previous
    percentage = (change / previous) * 100

    if change > 0:
        direction = "up"
    elif change < 0:
        direction = "down"
    else:
        direction = "neutral"

    return {
        "absolute": current,
        "change": change,
        "percentage": percentage,
        "direction": direction,
    }


def get_weekday_name(date_str: str) -> str:
    """Get weekday name from date string."""
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return dt.strftime("%A")
    except Exception:
        return ""


def parse_date_flexible(date_input) -> Optional[str]:
    """Parse date from various input formats."""
    if isinstance(date_input, str):
        formats = [
            "%Y-%m-%d",
            "%d-%m-%Y",
            "%d/%m/%Y",
            "%Y/%m/%d",
            "%d-%b-%Y",
            "%d %b %Y",
        ]
        for fmt in formats:
            try:
                return datetime.strptime(date_input, fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue
        return None
    elif isinstance(date_input, datetime):
        return date_input.strftime("%Y-%m-%d")
    elif hasattr(date_input, "strftime"):
        return date_input.strftime("%Y-%m-%d")

    return None


def calculate_mtd_period() -> tuple:
    """Get start and end of current month."""
    today = datetime.now().date()
    start = today.replace(day=1)
    return start, today


def get_days_in_month(year: int, month: int) -> int:
    """Get number of days in a month."""
    if month == 12:
        next_month = year + 1
        next_month_day = 1
    else:
        next_month = month + 1
        next_month_day = 1

    first_next_month = datetime(year, next_month, next_month_day).date()
    last_day = first_next_month - timedelta(days=1)
    return last_day.day


def get_month_working_days(year: int, month: int) -> int:
    """Get number of working days (Mon-Sat) in a month."""
    days = get_days_in_month(year, month)
    working_days = 0

    for day in range(1, days + 1):
        date = datetime(year, month, day).date()
        if date.weekday() < 6:  # Monday to Saturday
            working_days += 1

    return working_days


def calculate_projected_sales(
    mtd_sales: float, days_counted: int, total_days: int, weekday_type: str = "all"
) -> float:
    """Calculate projected month-end sales."""
    if days_counted == 0:
        return 0

    avg_daily = mtd_sales / days_counted

    if weekday_type == "all":
        return avg_daily * total_days
    else:
        # Calculate based on day type mix
        remaining_days = total_days - days_counted
        return mtd_sales + (avg_daily * remaining_days)


def get_status_color(value: float, target: float) -> str:
    """Get color based on achievement vs target."""
    if target == 0:
        return "gray"

    pct = (value / target) * 100

    if pct >= 100:
        return "green"
    elif pct >= 90:
        return "blue"
    elif pct >= 75:
        return "orange"
    else:
        return "red"


def get_status_emoji(value: float, target: float) -> str:
    """Get emoji based on achievement vs target."""
    if target == 0:
        return "⚪"

    pct = (value / target) * 100

    if pct >= 100:
        return "🟢"
    elif pct >= 90:
        return "🔵"
    elif pct >= 75:
        return "🟡"
    else:
        return "🔴"


def sanitize_filename(filename: str) -> str:
    """Sanitize filename for safe storage."""
    import re

    filename = re.sub(r"[^\w\s-]", "", filename)
    filename = re.sub(r"[-\s]+", "-", filename)
    return filename.strip("-")


def chunk_list(lst: List, chunk_size: int) -> List[List]:
    """Split list into chunks."""
    return [lst[i : i + chunk_size] for i in range(0, len(lst), chunk_size)]


def calculate_table_metrics(covers: int, tables_available: int = 100) -> Dict:
    """Calculate table-related metrics."""
    turns = covers / tables_available if tables_available > 0 else 0
    return {
        "covers": covers,
        "turns": round(turns, 1),
        "tables_used": min(covers, tables_available),
        "tables_available": tables_available,
    }
