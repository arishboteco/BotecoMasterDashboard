"""
Parser for Petpooja Complimentary Orders Summary (.xlsx).

Produces one dict per business date with the daily complimentary total.
These are merged into the daily_summary rows alongside Growth Report data
so that the MTD Complimentary KPI is populated.

Returns (rows, errors, meta) matching the standard parser interface.
"""

from __future__ import annotations

import re
from datetime import datetime
from io import BytesIO
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _norm(value: Any) -> str:
    """Normalise a cell value: strip, lowercase, collapse whitespace."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    s = str(value).replace("\xa0", " ").strip().lower()
    return re.sub(r"\s+", " ", s)


def _f(value: Any) -> float:
    """Convert a cell value to float, stripping currency symbols and commas."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return 0.0
    text = (
        str(value)
        .replace(",", "")
        .replace("₹", "")
        .replace("₹", "")
        .strip()
    )
    if not text or text.lower() in {"nan", "none"}:
        return 0.0
    try:
        return float(text)
    except ValueError:
        return 0.0


def _date_to_iso(value: Any) -> Optional[str]:
    """Parse a cell value to YYYY-MM-DD, returning None for non-date values."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d")
    s = str(value).strip().lower()
    if s in {"", "nan", "none", "total", "min.", "max.", "avg."}:
        return None
    ts = pd.to_datetime(value, errors="coerce")
    if pd.isna(ts):
        return None
    return ts.strftime("%Y-%m-%d")


def _load_frame(file_content: bytes, filename: str) -> Optional[pd.DataFrame]:
    """Load first sheet as a headerless DataFrame."""
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


def _extract_restaurant_name(df: pd.DataFrame) -> Optional[str]:
    """Find the restaurant name from the 'Restaurant Name:' row."""
    for i in range(min(10, len(df))):
        label = _norm(df.iloc[i, 0]) if df.shape[1] > 0 else ""
        if "restaurant name" in label:
            raw = str(df.iloc[i, 1]) if df.shape[1] > 1 else ""
            name = raw.strip()
            if name and name.lower() not in {"nan", "none", ""}:
                return name
    return None


def _header_index(df: pd.DataFrame) -> Optional[int]:
    """Find the header row containing 'Created Date', 'Grand Total', etc."""
    for i in range(min(15, len(df))):
        joined = " ".join(_norm(v) for v in df.iloc[i].values if _norm(v))
        if "created date" in joined and "grand total" in joined:
            return i
    return None


def _header_map(df: pd.DataFrame, header_idx: int) -> Dict[str, int]:
    """Return normalised-header → column-index mapping."""
    out: Dict[str, int] = {}
    for i, value in enumerate(df.iloc[header_idx].values):
        key = _norm(value)
        if key and key not in out:
            out[key] = i
    return out


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def parse_order_comp_summary(
    file_content: bytes,
    filename: str,
    location_id: Optional[int] = None,
) -> Tuple[List[Dict[str, Any]], List[str], Dict[str, Any]]:
    """Parse a Complimentary Orders Summary Excel file.

    Args:
        file_content:  Raw bytes of the .xlsx file.
        filename:      Original filename (used in error messages).
        location_id:   Pre-detected location; embedded in each output row.

    Returns:
        (rows, errors, meta)
        rows  — one dict per business date with complementary_amount + count.
        errors — human-readable blocking error strings.
        meta   — {"restaurant_name", "row_count", "order_count", ...}.
    """
    df = _load_frame(file_content, filename)
    if df is None or df.empty:
        return [], [f"Comp Summary {filename}: could not read file."], {}

    restaurant_name = _extract_restaurant_name(df)

    header_idx = _header_index(df)
    if header_idx is None:
        return [], [f"Comp Summary {filename}: header row not found."], {}

    colmap = _header_map(df, header_idx)
    data = df.iloc[header_idx + 1 :].copy()

    # Locate key columns
    idx_date = colmap.get("created date")
    idx_grand_total = colmap.get("grand total (₹)") or colmap.get("grand total")
    idx_taxable = colmap.get("taxable amount (₹)") or colmap.get("taxable amount")

    if idx_date is None:
        return [], [f"Comp Summary {filename}: 'Created Date' column not found."], {}
    if idx_grand_total is None and idx_taxable is None:
        return [], [f"Comp Summary {filename}: 'Grand Total' column not found."], {}

    # Use Grand Total if available, fall back to Taxable Amount
    idx_amount = idx_grand_total if idx_grand_total is not None else idx_taxable

    # Parse dates
    data["__date"] = data.iloc[:, idx_date].map(_date_to_iso)
    data = data[data["__date"].notna()].copy()
    if data.empty:
        return [], [f"Comp Summary {filename}: no dated rows found."], {}

    # Aggregate by date
    daily: Dict[str, Dict[str, Any]] = {}
    order_count = 0
    for _, row in data.iterrows():
        date_str = row["__date"]
        amount = _f(row.iloc[idx_amount]) if idx_amount < len(row) else 0.0
        if date_str not in daily:
            daily[date_str] = {
                "date": date_str,
                "complementary_amount": 0.0,
                "complementary_count": 0,
                "file_type": "order_comp_summary",
                "source_report": "order_comp_summary",
            }
            if location_id is not None:
                daily[date_str]["location_id"] = int(location_id)
        daily[date_str]["complementary_amount"] = round(
            daily[date_str]["complementary_amount"] + amount, 2
        )
        daily[date_str]["complementary_count"] += 1
        order_count += 1

    rows = sorted(daily.values(), key=lambda r: r["date"])

    # Extract period
    dates = sorted(daily.keys())
    period_start = dates[0] if dates else None
    period_end = dates[-1] if dates else None

    meta: Dict[str, Any] = {
        "restaurant_name": restaurant_name,
        "period_start": period_start,
        "period_end": period_end,
        "row_count": len(rows),
        "order_count": order_count,
    }
    return rows, [], meta
