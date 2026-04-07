"""Parse Dynamic Report CSV (per-bill order-level) into daily aggregated records.

This is the primary POS data source. Each row is one bill/order with:
- Bill Date, Bill No, Pax, Net Amount, Gross Sale, Discount, Service Charge
- CGST, SGST, category columns (Food, Liquor, Coffee, etc.)
- Payment columns (Cash, Card, Online, Wallet, Credit, Other Pmt)

Usage:
    records = parse_dynamic_report(content, filename)
    # Returns list of per-day dicts ready for save_daily_summary()
"""

from __future__ import annotations

from io import BytesIO, StringIO
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd


# Category column mapping: Dynamic Report column → clean name
_CATEGORY_MAP = {
    "carft beer": "Craft Beer",
    "coffee": "Coffee",
    "drink": "Drink",
    "food": "Food",
    "liquor": "Liquor",
    "soft drink": "Soft Drink",
    "other": "Other",
}

# Payment column mapping: Dynamic Report column → DB field
_PAYMENT_MAP = {
    "cash": "cash_sales",
    "card": "card_sales",
    "online": "gpay_sales",
    "wallet": "zomato_sales",
    "credit": "other_sales",
    "other pmt": "other_sales",
}


def _safe_float(val: Any) -> float:
    """Convert a value to float, treating '-', '', None, NaN as 0."""
    if val is None:
        return 0.0
    s = str(val).strip()
    if s in ("-", "", "nan", "None"):
        return 0.0
    try:
        return float(s)
    except ValueError:
        return 0.0


def _safe_int(val: Any) -> int:
    """Convert a value to int, treating '-', '', None, NaN as 0."""
    if val is None:
        return 0
    s = str(val).strip()
    if s in ("-", "", "nan", "None"):
        return 0
    try:
        return int(float(s))
    except ValueError:
        return 0


def _meal_from_time(ts_val: Any) -> Optional[str]:
    """Classify a datetime value as 'Lunch' (before 18:00) or 'Dinner' (18:00+).

    Args:
        ts_val: Raw value from the 'Created Date Time' column.

    Returns:
        'Lunch', 'Dinner', or None if unparseable.
    """
    if ts_val is None:
        return None
    s = str(ts_val).strip()
    if s in ("", "nan", "None"):
        return None
    try:
        ts = pd.Timestamp(s)
    except Exception:
        return None
    if pd.isna(ts):
        return None
    if ts.hour < 18:
        return "Lunch"
    return "Dinner"


def parse_dynamic_report(
    content: bytes, filename: str
) -> Tuple[Optional[List[Dict[str, Any]]], List[str]]:
    """Parse Dynamic Report CSV into per-day aggregated records.

    Args:
        content: Raw CSV bytes
        filename: Original filename (for error messages)

    Returns:
        Tuple of (list of per-day dicts, list of notes/warnings)
        Returns (None, notes) on fatal error.
    """
    notes: List[str] = []

    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            return None, [f"Cannot decode {filename}: not valid UTF-8"]

    try:
        df = pd.read_csv(StringIO(text), dtype=str)
    except Exception as ex:
        return None, [f"Cannot parse {filename} as CSV: {ex}"]

    if df.empty:
        return None, [f"{filename} is empty"]

    # Normalize column names
    df.columns = [c.strip() for c in df.columns]
    col_map = {c.lower(): c for c in df.columns}

    # Verify required columns
    required = ["bill date", "bill no", "pax", "net amount", "gross sale"]
    missing = [r for r in required if r not in col_map]
    if missing:
        return None, [f"{filename} missing required columns: {', '.join(missing)}"]

    # Extract restaurant name (column A) for location routing
    rest_col = col_map.get("restaurant")
    restaurant_name: Optional[str] = None
    if rest_col and not df.empty:
        first_val = str(df[rest_col].iloc[0]).strip()
        if first_val and first_val.lower() not in ("", "nan", "none"):
            restaurant_name = first_val

    # Filter to successful orders only
    if "bill status" in col_map:
        status_col = col_map["bill status"]
        before = len(df)
        df = df[df[status_col].str.strip() == "SuccessOrder"]
        after = len(df)
        notes.append(f"Filtered {before - after} non-SuccessOrder rows from {filename}")
    elif "status" in col_map:
        status_col = col_map["status"]
        before = len(df)
        df = df[df[status_col].str.strip().str.lower() == "success"]
        after = len(df)
        notes.append(f"Filtered {before - after} non-success rows from {filename}")

    if df.empty:
        return None, [f"No SuccessOrder rows found in {filename}"]

    # Get column references
    date_col = col_map["bill date"]
    bill_col = col_map["bill no"]
    pax_col = col_map["pax"]
    net_col = col_map["net amount"]
    gross_col = col_map["gross sale"]
    disc_col = col_map.get("discount")
    sc_col = col_map.get("service charge (10)")
    cgst_col = col_map.get("cgst (2.5)")
    sgst_col = col_map.get("sgst (2.5)")
    cdt_col = col_map.get("created date time")

    # Group by date
    days: Dict[str, Dict[str, Any]] = {}

    for _, row in df.iterrows():
        date_raw = str(row.get(date_col, "")).strip()[:10]
        if not date_raw or date_raw == "nan":
            continue

        if date_raw not in days:
            days[date_raw] = {
                "date": date_raw,
                "covers": 0,
                "net_total": 0.0,
                "gross_total": 0.0,
                "discount": 0.0,
                "service_charge": 0.0,
                "cgst": 0.0,
                "sgst": 0.0,
                "cash_sales": 0.0,
                "card_sales": 0.0,
                "gpay_sales": 0.0,
                "zomato_sales": 0.0,
                "other_sales": 0.0,
                "order_count": 0,
                "bills": set(),
                "categories": {},
                "meals": {},
            }

        day = days[date_raw]

        # Basic aggregates
        day["covers"] += _safe_int(row.get(pax_col, 0))
        day["net_total"] += _safe_float(row.get(net_col, 0))
        day["gross_total"] += _safe_float(row.get(gross_col, 0))
        day["discount"] += _safe_float(row.get(disc_col, 0)) if disc_col else 0.0
        day["service_charge"] += _safe_float(row.get(sc_col, 0)) if sc_col else 0.0
        day["cgst"] += _safe_float(row.get(cgst_col, 0)) if cgst_col else 0.0
        day["sgst"] += _safe_float(row.get(sgst_col, 0)) if sgst_col else 0.0

        # Payment breakdown
        for dyn_col, db_field in _PAYMENT_MAP.items():
            if dyn_col in col_map:
                day[db_field] += _safe_float(row.get(col_map[dyn_col], 0))

        # Track unique bills for order count
        bill_no = str(row.get(bill_col, "")).strip()
        if bill_no and bill_no != "nan":
            day["bills"].add(bill_no)

        # Category breakdown
        for dyn_col, clean_name in _CATEGORY_MAP.items():
            if dyn_col in col_map:
                val = _safe_float(row.get(col_map[dyn_col], 0))
                if val > 0:
                    day["categories"][clean_name] = (
                        day["categories"].get(clean_name, 0.0) + val
                    )

        # Meal period (service) breakdown
        if cdt_col:
            meal = _meal_from_time(row.get(cdt_col))
            if meal:
                net_val = _safe_float(row.get(net_col, 0))
                day["meals"][meal] = day["meals"].get(meal, 0.0) + net_val

    # Build output records
    results: List[Dict[str, Any]] = []
    for date_str in sorted(days.keys()):
        day = days[date_str]
        bill_count = len(day["bills"])

        # Build category list
        categories = [
            {"category": name, "qty": 0, "amount": round(amt, 2)}
            for name, amt in sorted(day["categories"].items(), key=lambda x: -x[1])
        ]

        services = [
            {"type": k, "amount": round(v, 2)}
            for k, v in sorted(day["meals"].items(), key=lambda x: -x[1])
            if v > 0
        ]

        record = {
            "date": date_str,
            "covers": day["covers"],
            "net_total": round(day["net_total"], 2),
            "gross_total": round(day["gross_total"], 2),
            "discount": round(day["discount"], 2),
            "service_charge": round(day["service_charge"], 2),
            "cgst": round(day["cgst"], 2),
            "sgst": round(day["sgst"], 2),
            "cash_sales": round(day["cash_sales"], 2),
            "card_sales": round(day["card_sales"], 2),
            "gpay_sales": round(day["gpay_sales"], 2),
            "zomato_sales": round(day["zomato_sales"], 2),
            "other_sales": round(day["other_sales"], 2),
            "order_count": bill_count,
            "categories": categories,
            "services": services,
            "file_type": "dynamic_report",
            "restaurant": restaurant_name,
        }
        results.append(record)

    total_orders = sum(r["order_count"] for r in results)
    total_covers = sum(r["covers"] for r in results)
    notes.append(
        f"Parsed {len(results)} day(s), {total_orders} orders, {total_covers} covers from {filename}"
    )

    return results, notes
