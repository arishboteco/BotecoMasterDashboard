"""
Parser for Petpooja Item Report With Customer/Order Details (.xlsx).

Produces category-level aggregations (not item-level rows) for
category_summary upsert.  Financial source-of-truth remains the
Growth Report; this parser only contributes category breakdown.

Returns (rows, errors, meta).
"""

from __future__ import annotations

import re
from io import BytesIO
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

# ---------------------------------------------------------------------------
# Category normalisation rules
# ---------------------------------------------------------------------------

# Maps a normalised group_name substring → standardised dashboard category.
# Checked in order; first match wins.
_CATEGORY_RULES: List[Tuple[str, str]] = [
    ("food - pfa", "Food"),
    ("food", "Food"),
    ("liquor", "Liquor"),
    ("wine", "Liquor"),
    ("spirits", "Liquor"),
    ("beer", "Liquor"),
    ("soft drink", "Soft Beverages"),
    ("soft beverages", "Soft Beverages"),
    ("aerated", "Soft Beverages"),
    ("beverage", "Soft Beverages"),
    ("mocktail", "Soft Beverages"),
    ("coffee", "Coffee"),
    ("hot beverages", "Coffee"),
]


def _normalize_category(group_name: str) -> str:
    """Map a group_name to the standardised dashboard category."""
    key = group_name.strip().lower()
    for fragment, label in _CATEGORY_RULES:
        if fragment in key:
            return label
    # No rule matched — preserve the original group name as-is
    return group_name.strip()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _norm(value: Any) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return re.sub(r"\s+", " ", str(value).replace("\xa0", " ").strip().lower())


def _f(value: Any) -> float:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return 0.0
    text = str(value).replace(",", "").replace("₹", "").strip()
    if not text or text.lower() in {"nan", "none"}:
        return 0.0
    try:
        return float(text)
    except ValueError:
        return 0.0


def _load_frame(file_content: bytes, filename: str) -> Optional[pd.DataFrame]:
    bio = BytesIO(file_content)
    head = file_content[:2500].lower()
    if b"<html" in head or b"<!doctype" in head:
        try:
            dfs = pd.read_html(bio)
            return pd.concat(dfs, ignore_index=True) if dfs else None
        except Exception:
            return None
    for engine in (None, "openpyxl", "xlrd"):
        try:
            bio.seek(0)
            kwargs = {"engine": engine} if engine else {}
            return pd.read_excel(bio, sheet_name=0, header=None, **kwargs)
        except Exception:
            continue
    return None


def _header_index(df: pd.DataFrame) -> Optional[int]:
    """Find the row containing column headers (expects Sub Total + Final Total)."""
    for i in range(min(20, len(df))):
        joined = " ".join(_norm(v) for v in df.iloc[i].values if _norm(v))
        if "sub total" in joined and "final total" in joined:
            return i
    return None


def _header_map(df: pd.DataFrame, header_idx: int) -> Dict[str, int]:
    """Return normalised-header → first-column-index mapping."""
    out: Dict[str, int] = {}
    for i, value in enumerate(df.iloc[header_idx].values):
        key = _norm(value)
        if key and key not in out:
            out[key] = i
    return out


def _col(row: pd.Series, colmap: Dict[str, int], *names: str) -> Any:
    for name in names:
        idx = colmap.get(name)
        if idx is not None and idx < len(row):
            return row.iloc[idx]
    return None


def _cell(row: pd.Series, col: Optional[int]) -> float:
    """Return _f(row[col]) or 0.0 if col is None or out of range."""
    if col is None or col >= len(row):
        return 0.0
    return _f(row.iloc[col])


def _extract_period(df: pd.DataFrame) -> Tuple[Optional[str], Optional[str]]:
    for i in range(min(10, len(df))):
        values = [
            str(v)
            for v in df.iloc[i].values
            if str(v).strip().lower() not in {"nan", "none", ""}
        ]
        joined = " ".join(values)
        match = re.search(r"(\d{4}-\d{2}-\d{2})\s+to\s+(\d{4}-\d{2}-\d{2})", joined)
        if match:
            return match.group(1), match.group(2)
    return None, None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def parse_item_report_category_summary(
    file_content: bytes,
    filename: str,
    location_id: Optional[int] = None,
) -> Tuple[List[Dict[str, Any]], List[str], Dict[str, Any]]:
    """Parse an Item Report, aggregating to category-level rows per date.

    Args:
        file_content:  Raw bytes of the .xlsx file.
        filename:      Original filename (used in error messages).
        location_id:   Pre-detected location; embedded in each output row.

    Returns:
        (rows, errors, meta)
        rows  — one dict per (date, category_name), shaped for
                category_summary upsert.
        errors — blocking error strings (non-empty = import blocked).
        meta   — {"period_start", "period_end", "row_count"}.
    """
    df = _load_frame(file_content, filename)
    if df is None or df.empty:
        return [], [f"Item Report {filename}: could not read file."], {}

    header_idx = _header_index(df)
    if header_idx is None:
        return [], [f"Item Report {filename}: header row not found."], {}

    colmap = _header_map(df, header_idx)
    data = df.iloc[header_idx + 1 :].copy()
    data.columns = range(data.shape[1])

    # Resolve required columns
    date_col = colmap.get("date")
    if date_col is None:
        return [], [f"Item Report {filename}: Date column not found."], {}

    status_col = colmap.get("status")
    timestamp_col = colmap.get("timestamp")
    qty_col = colmap.get("qty.")
    sub_total_col = colmap.get("sub total")
    discount_col = colmap.get("discount")
    tax_col = colmap.get("tax")
    final_total_col = colmap.get("final total")
    cgst_col = colmap.get("cgst amount")
    sgst_col = colmap.get("sgst amount")
    sc_col = colmap.get("service charge amount")

    if sub_total_col is None or final_total_col is None:
        return [], [f"Item Report {filename}: Sub Total / Final Total columns not found."], {}

    # Accumulate per (date_str, category_name) bucket
    Bucket = Dict[str, Any]
    buckets: Dict[Tuple[str, str], Bucket] = {}
    # Separately track complimentary and cancelled amounts
    comp_buckets: Dict[Tuple[str, str], float] = {}
    canc_buckets: Dict[Tuple[str, str], float] = {}
    service_buckets: Dict[str, Dict[str, float]] = {}

    for _, row in data.iterrows():
        raw_date = row.iloc[date_col] if date_col < len(row) else None
        if raw_date is None or _norm(raw_date) in {"", "nan", "none", "total"}:
            continue
        date_str = pd.to_datetime(raw_date, errors="coerce")
        if pd.isna(date_str):
            continue
        date_str = date_str.strftime("%Y-%m-%d")

        raw_status = str(row.iloc[status_col]).strip() if status_col is not None else "Success"
        status = raw_status.strip().lower()

        # Use Category for analytics labels and keep Group Name for normalization.
        group_raw = str(_col(row, colmap, "group name") or "").strip()
        cat_raw = str(_col(row, colmap, "category") or "").strip()
        category_name = cat_raw
        if not category_name or category_name.lower() in {"nan", "none"}:
            category_name = group_raw
        if not category_name or category_name.lower() in {"nan", "none"}:
            category_name = "Other"

        group_name = group_raw
        if not group_name or group_name.lower() in {"nan", "none"}:
            group_name = category_name

        key = (date_str, category_name)

        final_total_val = _f(row.iloc[final_total_col] if final_total_col < len(row) else 0)

        if status == "complimentary":
            comp_buckets[key] = comp_buckets.get(key, 0.0) + final_total_val
            continue
        if status == "cancelled":
            canc_buckets[key] = canc_buckets.get(key, 0.0) + abs(final_total_val)
            continue
        if status != "success":
            continue

        if timestamp_col is not None and timestamp_col < len(row):
            timestamp = pd.to_datetime(row.iloc[timestamp_col], errors="coerce")
            if not pd.isna(timestamp):
                service_type = "Lunch" if int(timestamp.hour) < 18 else "Dinner"
                service_buckets.setdefault(date_str, {"Lunch": 0.0, "Dinner": 0.0})[
                    service_type
                ] += _cell(row, sub_total_col) - _cell(row, discount_col)

        if key not in buckets:
            normalized = _normalize_category(group_name)
            buckets[key] = {
                "date": date_str,
                "category_name": category_name,
                "group_name": group_name,
                "normalized_category": normalized,
                "qty": 0,
                "sub_total": 0.0,
                "discount": 0.0,
                "tax": 0.0,
                "final_total": 0.0,
                "cgst_amount": 0.0,
                "sgst_amount": 0.0,
                "service_charge_amount": 0.0,
            }

        b = buckets[key]
        b["qty"] += int(round(_cell(row, qty_col)))
        b["sub_total"] += _cell(row, sub_total_col)
        b["discount"] += _cell(row, discount_col)
        b["tax"] += _cell(row, tax_col)
        b["final_total"] += _cell(row, final_total_col)
        b["cgst_amount"] += _cell(row, cgst_col)
        b["sgst_amount"] += _cell(row, sgst_col)
        b["service_charge_amount"] += _cell(row, sc_col)

    rows: List[Dict[str, Any]] = []
    for (date_str, category_name), b in buckets.items():
        key = (date_str, category_name)
        row_out: Dict[str, Any] = {
            "date": b["date"],
            "category_name": b["category_name"],
            "group_name": b["group_name"],
            "normalized_category": b["normalized_category"],
            "qty": b["qty"],
            "net_amount": round(b["sub_total"] - b["discount"], 2),
            "sub_total": round(b["sub_total"], 2),
            "discount": round(b["discount"], 2),
            "tax": round(b["tax"], 2),
            "final_total": round(b["final_total"], 2),
            "cgst_amount": round(b["cgst_amount"], 2),
            "sgst_amount": round(b["sgst_amount"], 2),
            "service_charge_amount": round(b["service_charge_amount"], 2),
            "complimentary_amount": round(comp_buckets.get(key, 0.0), 2),
            "cancelled_amount": round(canc_buckets.get(key, 0.0), 2),
            "source_report": "item_report_customer_order_details",
            "file_type": "item_order_details_category",
        }
        if location_id is not None:
            row_out["location_id"] = int(location_id)
        rows.append(row_out)

    period_start, period_end = _extract_period(df)
    service_sales_by_date = {
        date: [
            {"type": service_type, "amount": round(amount, 2)}
            for service_type, amount in buckets_by_service.items()
            if amount > 0
        ]
        for date, buckets_by_service in service_buckets.items()
    }
    meta: Dict[str, Any] = {
        "period_start": period_start,
        "period_end": period_end,
        "row_count": len(rows),
        "service_sales_by_date": service_sales_by_date,
    }
    return rows, [], meta
