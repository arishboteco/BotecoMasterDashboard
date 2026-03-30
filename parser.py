import pandas as pd
import openpyxl
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from io import BytesIO
import config


def parse_sales_summary(file_content: bytes, filename: str) -> Optional[Dict]:
    """Parse sales summary XLSX file."""
    try:
        # Read Excel file
        df = pd.read_excel(BytesIO(file_content), sheet_name=None)

        # Try to find the main data sheet
        for sheet_name, df_sheet in df.items():
            result = _parse_sheet(df_sheet, filename)
            if result:
                return result

        return None
    except Exception as e:
        print(f"Error parsing file: {e}")
        return None


def _parse_sheet(df: pd.DataFrame, filename: str) -> Optional[Dict]:
    """Parse a single sheet and extract data."""

    # Convert to string to handle mixed types
    df_str = df.astype(str)

    # Try to find date in first row or first column
    date = None
    data = {}

    # Look for key indicators in the data
    for idx, row in df_str.iterrows():
        row_values = " ".join([str(v) for v in row.values]).lower()

        # Find date patterns
        if not date:
            for val in row.values:
                if _looks_like_date(val):
                    parsed_date = _parse_date(str(val))
                    if parsed_date:
                        date = parsed_date
                        break

        # Extract key metrics based on keywords
        if "covers" in row_values and "eod" not in row_values:
            data["covers"] = _extract_number(row_values, ["covers", "covers:"])

        if "turns" in row_values:
            data["turns"] = _extract_decimal(row_values, ["turns"])

        if "gross" in row_values or "total" in row_values:
            if "eod" in row_values or "gross" in row_values:
                data["gross_total"] = _extract_number(row_values, ["gross", "total"])

        if "cash" in row_values and "sale" in row_values:
            data["cash_sales"] = _extract_number(row_values, ["cash"])

        if "card" in row_values and "sale" in row_values:
            data["card_sales"] = _extract_number(row_values, ["card"])

        if "gpay" in row_values or "google" in row_values or "upi" in row_values:
            data["gpay_sales"] = _extract_number(row_values, ["gpay", "google", "upi"])

        if "zomato" in row_values:
            data["zomato_sales"] = _extract_number(row_values, ["zomato"])

        if "service" in row_values and "charge" in row_values:
            data["service_charge"] = _extract_number(
                row_values, ["service charge", "service"]
            )

        if "cgst" in row_values:
            data["cgst"] = _extract_number(row_values, ["cgst"])

        if "sgst" in row_values:
            data["sgst"] = _extract_number(row_values, ["sgst"])

        if "discount" in row_values:
            data["discount"] = _extract_number(row_values, ["discount"])

        if "complimentary" in row_values or "complementry" in row_values:
            data["complimentary"] = _extract_number(
                row_values, ["complimentary", "complementry"]
            )

    if date:
        return {
            "date": date,
            "filename": filename,
            "file_type": "sales_summary",
            **{k: v for k, v in data.items() if v is not None},
        }

    return None


def _looks_like_date(val: str) -> bool:
    """Check if a value looks like a date."""
    val = str(val).strip().lower()
    date_patterns = [
        "2026",
        "2025",
        "2024",
        "jan",
        "feb",
        "mar",
        "apr",
        "may",
        "jun",
        "jul",
        "aug",
        "sep",
        "oct",
        "nov",
        "dec",
    ]
    return any(pattern in val for pattern in date_patterns)


def _parse_date(val: str) -> Optional[str]:
    """Parse date string to YYYY-MM-DD format."""
    val = str(val).strip()

    formats = [
        "%Y-%m-%d",
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%d-%b-%Y",
        "%d-%B-%Y",
        "%b-%d-%Y",
        "%d %b %Y",
        "%d %B %Y",
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(val, fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue

    return None


def _extract_number(text: str, keywords: List[str]) -> Optional[float]:
    """Extract number from text based on keywords."""
    import re

    # Find pattern like "keyword: value" or "keyword value"
    for keyword in keywords:
        patterns = [
            rf"{keyword}\s*[:\-]?\s*([\d,]+\.?\d*)",
            rf"([\d,]+\.?\d*)\s*{keyword}",
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                try:
                    return float(matches[0].replace(",", ""))
                except ValueError:
                    continue

    return None


def _extract_decimal(text: str, keywords: List[str]) -> Optional[float]:
    """Extract decimal number from text."""
    import re

    for keyword in keywords:
        pattern = rf"{keyword}\s*[:\-]?\s*([\d.]+)"
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            try:
                return float(matches[0])
            except ValueError:
                continue

    return None


def parse_category_sales(file_content: bytes, filename: str) -> Optional[List[Dict]]:
    """Parse category sales file."""
    try:
        df = pd.read_excel(BytesIO(file_content), sheet_name=None)
        categories = []

        for sheet_name, df_sheet in df.items():
            for idx, row in df_sheet.iterrows():
                row_str = " ".join([str(v) for v in row.values]).lower()

                # Look for category patterns
                category_keywords = [
                    "food",
                    "liquor",
                    "beer",
                    "soft",
                    "coffee",
                    "tobacco",
                    "beverage",
                ]
                for kw in category_keywords:
                    if kw in row_str:
                        amount = _extract_number(
                            row_str, [kw, "amount", "amt", "revenue", "sales"]
                        )
                        qty = _extract_number(row_str, ["qty", "quantity", "qty."])
                        if amount:
                            categories.append(
                                {
                                    "category": _normalize_category(kw),
                                    "qty": int(qty) if qty else 0,
                                    "amount": amount,
                                }
                            )

        return categories if categories else None
    except Exception as e:
        print(f"Error parsing category file: {e}")
        return None


def _normalize_category(keyword: str) -> str:
    """Normalize category names."""
    mapping = {
        "food": "Food",
        "liquor": "Liquor",
        "beer": "Beer",
        "soft": "Soft Beverages",
        "coffee": "Coffee",
        "tobacco": "Tobacco",
        "beverage": "Beverages",
    }
    return mapping.get(keyword.lower(), keyword.title())


def calculate_mtd_metrics(location_id: int, target_monthly: float) -> Dict:
    """Calculate Month-to-Date metrics from stored data."""
    from database import get_summaries_for_month

    today = datetime.now()
    summaries = get_summaries_for_month(location_id, today.year, today.month)

    total_covers = sum(s.get("covers", 0) for s in summaries)
    total_sales = sum(s.get("net_total", 0) for s in summaries)
    total_discount = sum(s.get("discount", 0) for s in summaries)
    days_counted = len([s for s in summaries if s.get("net_total", 0) > 0])

    avg_daily = total_sales / days_counted if days_counted > 0 else 0
    pct_target = (total_sales / target_monthly) * 100 if target_monthly > 0 else 0

    return {
        "mtd_total_covers": total_covers,
        "mtd_net_sales": total_sales,
        "mtd_discount": total_discount,
        "mtd_avg_daily": avg_daily,
        "mtd_target": target_monthly,
        "mtd_pct_target": pct_target,
        "days_counted": days_counted,
    }


def calculate_derived_metrics(data: Dict) -> Dict:
    """Calculate derived metrics from raw data."""
    # Calculate APC (Average Per Cover)
    if data.get("covers", 0) > 0:
        data["apc"] = data.get("net_total", 0) / data["covers"]
    else:
        data["apc"] = 0

    # Calculate turns (simplified: covers / assumed tables)
    # Assuming ~100 tables
    if data.get("covers", 0) > 0:
        data["turns"] = round(data["covers"] / 100, 1)
    else:
        data["turns"] = 0

    # Calculate percentage of target
    if data.get("target", 0) > 0:
        data["pct_target"] = round((data.get("net_total", 0) / data["target"]) * 100, 2)
    else:
        data["pct_target"] = 0

    return data


def parse_manual_entry(form_data: Dict) -> Dict:
    """Parse data from manual entry form."""
    result = {
        "date": form_data.get("date"),
        "filename": "manual_entry",
        "file_type": "manual",
        "covers": int(form_data.get("covers", 0) or 0),
        "gross_total": float(form_data.get("gross_total", 0) or 0),
        "net_total": float(form_data.get("net_total", 0) or 0),
        "cash_sales": float(form_data.get("cash_sales", 0) or 0),
        "card_sales": float(form_data.get("card_sales", 0) or 0),
        "gpay_sales": float(form_data.get("gpay_sales", 0) or 0),
        "zomato_sales": float(form_data.get("zomato_sales", 0) or 0),
        "other_sales": float(form_data.get("other_sales", 0) or 0),
        "service_charge": float(form_data.get("service_charge", 0) or 0),
        "cgst": float(form_data.get("cgst", 0) or 0),
        "sgst": float(form_data.get("sgst", 0) or 0),
        "discount": float(form_data.get("discount", 0) or 0),
        "complimentary": float(form_data.get("complimentary", 0) or 0),
        "target": float(form_data.get("target", 0) or 0),
    }

    # Calculate derived metrics
    result = calculate_derived_metrics(result)

    # Parse categories if provided
    categories = []
    for i in range(1, 7):
        cat_name = form_data.get(f"cat_{i}_name")
        cat_qty = form_data.get(f"cat_{i}_qty")
        cat_amount = form_data.get(f"cat_{i}_amount")

        if cat_name and cat_amount:
            categories.append(
                {
                    "category": cat_name,
                    "qty": int(cat_qty or 0),
                    "amount": float(cat_amount or 0),
                }
            )

    if categories:
        result["categories"] = categories

    # Parse services if provided
    services = []
    for svc_type in ["Breakfast", "Lunch", "Dinner", "Delivery", "Events", "Party"]:
        svc_amount = form_data.get(f"svc_{svc_type.lower()}_amount")
        if svc_amount:
            services.append({"type": svc_type, "amount": float(svc_amount or 0)})

    if services:
        result["services"] = services

    return result


def validate_data(data: Dict) -> Tuple[bool, List[str]]:
    """Validate parsed data."""
    errors = []

    if not data.get("date"):
        errors.append("Date is required")

    if data.get("gross_total", 0) <= 0:
        errors.append("Gross total should be greater than 0")

    if data.get("net_total", 0) <= 0:
        errors.append("Net total should be greater than 0")

    return len(errors) == 0, errors
