"""
Parser for Petpooja Growth Report Day Wise (.xlsx).

Produces one dict per business date, shaped for daily_summary upsert.
Returns (rows, errors, meta) so callers can surface parse failures.
"""

from __future__ import annotations

import re
from datetime import datetime
from io import BytesIO
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

# ---------------------------------------------------------------------------
# Payment column mappings
# ---------------------------------------------------------------------------

# Any payment column whose normalised name is a key here will be stored in
# the corresponding DB field.  Values are summed across duplicate columns.
ALLOWED_PAYMENT_COLUMNS: Dict[str, str] = {
    "cash": "cash_sales",
    "card": "card_sales",
    "due payment": "due_payment_sales",
    # "Not Paid" is Petpooja's older label for the same concept
    "not paid": "due_payment_sales",
    "wallet": "wallet_sales",
    "upi": "upi_sales",
    # G PAY variants (double-space, trailing parens) all normalise to one key
    "other [g pay]": "gpay_sales",
    "other [gpay]": "gpay_sales",
    "other [g pay]()": "gpay_sales",
    "other [bank transfer]": "bank_transfer_sales",
    "other [boh]": "boh_sales",
}

# Columns that are silently ignored when their total is zero.
# If they carry non-zero values the import is BLOCKED (unmapped payment).
IGNORED_ZERO_PAYMENT_COLUMNS = {
    "cod",
    "other [upi]",
    "other [zomato]",
    "other [swiggy]",
    "other [dineout]",
    "other [zomato delivery]",
    "other [swiggy delivery]",
    "other [coupon]",
    "other [razorpay]",
}

# Non-payment structural fields — used to skip them in payment validation.
BASE_FIELDS = {
    "date",
    "orders",
    "invoice nos.",
    "invoice nos",
    "my amount (₹)",
    "my amount",
    "discount (₹)",
    "discount",
    "net sales (₹)(m.a - d)",
    "net sales",
    "delivery charge",
    "container charge",
    "service charge",
    "total tax (₹)",
    "total tax",
    "round off",
    "waived off",
    "total (₹)",
    "total",
    "online tax calculated",
    "gst paid by merchant",
    "gst paid by ecommerce",
    "non taxable",
    "amount (cgst)",
    "cgst",
    "amount (sgst)",
    "sgst",
    "amount (cgst@2.5)",
    "cgst@2.5",
    "amount (sgst@2.5)",
    "sgst@2.5",
    "amount (gst on sevice charge)",
    "amount (gst on service charge)",
    "gst on sevice charge",
    "gst on service charge",
    "amount (service charge)",
    "delivery orders",
    "delivery",
    "pick up orders",
    "pick up",
    "dine in orders",
    "dine in",
    "menu qr code orders",
    "menu qr code cod",
    "menu qr code other",
    "menu qr code",
    "expenses",
    "pax",
    "covers",
}

# Maps normalised header → DB field name for non-payment columns.
# NOTE: Some target fields intentionally have both full and short header variants.
# The extraction loop below must not let a missing short variant overwrite a
# previously found full variant with zero.
FIELD_MAP: Dict[str, str] = {
    "orders": "order_count",
    "my amount (₹)": "my_amount",
    "my amount": "my_amount",
    "discount (₹)": "discount",
    "discount": "discount",
    "net sales (₹)(m.a - d)": "net_total",
    "net sales": "net_total",
    "total tax (₹)": "total_tax",
    "total tax": "total_tax",
    "round off": "round_off",
    "total (₹)": "gross_total",
    "total": "gross_total",
    "cgst": "cgst",
    "sgst": "sgst",
    "gst on sevice charge": "gst_on_service_charge",
    "gst on service charge": "gst_on_service_charge",
    "delivery": "delivery_sales",
    "pick up": "pickup_sales",
    "dine in": "dine_in_sales",
    "menu qr code": "menu_qr_sales",
    "expenses": "expenses",
    "pax": "covers",
    "covers": "covers",
}

# Fields deliberately handled outside the generic FIELD_MAP loop.
_MANUAL_FIELDS = {"service charge", "gst on sevice charge", "gst on service charge"}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _norm(value: Any) -> str:
    """Normalise a cell value: strip, lowercase, collapse whitespace."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    s = str(value).replace("\xa0", " ").strip().lower()
    return re.sub(r"\s+", " ", s)


def _clean_payment_header(value: Any) -> str:
    """Normalise a payment column header, collapsing whitespace inside brackets."""
    s = _norm(value)
    s = re.sub(r"\[\s+", "[", s)   # "[ G PAY]"  → "[G PAY]"
    s = re.sub(r"\s+\]", "]", s)   # "[G PAY ]"  → "[G PAY]"
    s = re.sub(r"\s+", " ", s)     # "g  pay"    → "g pay"
    # Normalise trailing empty parens
    if s.endswith("()"):
        s = s[:-2].rstrip()
    return s


def _f(value: Any) -> float:
    """Convert a cell value to float, stripping currency symbols and commas."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return 0.0
    text = (
        str(value)
        .replace(",", "")
        .replace("₹", "")
        .replace("₹", "")  # ₹ unicode
        .strip()
    )
    if not text or text.lower() in {"nan", "none"}:
        return 0.0
    try:
        return float(text)
    except ValueError:
        return 0.0


def _i(value: Any) -> int:
    return int(round(_f(value)))


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
    """Find the row that contains the main column headers."""
    for i in range(min(40, len(df))):
        joined = " ".join(_norm(v) for v in df.iloc[i].values if _norm(v))
        if (
            "net sales" in joined
            and "total tax" in joined
            and "cash" in joined
            and "card" in joined
        ):
            return i
    return None


def _header_map(df: pd.DataFrame, header_idx: int) -> Dict[str, int]:
    """Return normalised-header → first-column-index mapping."""
    out: Dict[str, int] = {}
    for i, value in enumerate(df.iloc[header_idx].values):
        key = _clean_payment_header(value)
        if key and key not in out:
            out[key] = i
    return out


def _last_col_for(df: pd.DataFrame, header_idx: int, target: str) -> Optional[int]:
    """Return the column index of the LAST occurrence of target in the header row.

    Some reports repeat "Service Charge" as both a summary column (often zero)
    and as the actual amount inside the tax breakdown section.  Using the last
    occurrence picks up the non-zero detailed value in those cases.
    """
    last: Optional[int] = None
    for i, value in enumerate(df.iloc[header_idx].values):
        if _clean_payment_header(value) == target:
            last = i
    return last


def _payment_columns(
    colmap: Dict[str, int], data: pd.DataFrame
) -> Tuple[Dict[str, int], List[str]]:
    """Split header map into known-payment columns and a list of unmapped ones.

    Returns (payments_dict, unmapped_names).
    unmapped_names is non-empty only for columns with non-zero totals that are
    not in the allowed or ignored sets.
    """
    payments: Dict[str, int] = {}
    unmapped: List[str] = []
    for header, idx in colmap.items():
        if header in ALLOWED_PAYMENT_COLUMNS:
            payments[header] = idx
            continue
        # Treat anything that looks payment-shaped but is not in the allow-list
        # as potentially problematic.
        is_payment_shaped = header.startswith("other [") or header in {
            "cash",
            "card",
            "due payment",
            "not paid",
            "wallet",
            "upi",
        }
        if not is_payment_shaped:
            continue
        col_total = (
            float(data.iloc[:, idx].map(_f).sum()) if idx < data.shape[1] else 0.0
        )
        if abs(col_total) < 0.005:
            continue  # zero column — silently ignore
        if header in IGNORED_ZERO_PAYMENT_COLUMNS:
            # Was expected zero but has value — block
            unmapped.append(header)
        elif header not in BASE_FIELDS:
            unmapped.append(header)
    return payments, sorted(set(unmapped))


def _value(row: pd.Series, colmap: Dict[str, int], *names: str) -> Any:
    for name in names:
        idx = colmap.get(name)
        if idx is not None and idx < len(row):
            return row.iloc[idx]
    return 0


def _extract_period(df: pd.DataFrame) -> Tuple[Optional[str], Optional[str]]:
    """Try to extract period_start / period_end from the report header rows."""
    if df.empty:
        return None, None
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


def parse_growth_report_day_wise(
    file_content: bytes,
    filename: str,
    location_id: Optional[int] = None,
) -> Tuple[List[Dict[str, Any]], List[str], Dict[str, Any]]:
    """Parse a Growth Report Day Wise Excel file.

    Args:
        file_content:  Raw bytes of the .xlsx file.
        filename:      Original filename (used in error messages).
        location_id:   Pre-detected location; embedded in each output row.

    Returns:
        (rows, errors, meta)
        rows  — one dict per business date, shaped for daily_summary upsert.
        errors — human-readable blocking error strings (non-empty = import blocked).
        meta   — {"period_start", "period_end", "row_count", ...}.
    """
    df = _load_frame(file_content, filename)
    if df is None or df.empty:
        return [], [f"Growth Report {filename}: could not read file."], {}

    header_idx = _header_index(df)
    if header_idx is None:
        return [], [f"Growth Report {filename}: header row not found."], {}

    colmap = _header_map(df, header_idx)
    data = df.iloc[header_idx + 1 :].copy()

    idx_date = colmap.get("date")
    if idx_date is None:
        return [], [f"Growth Report {filename}: Date column not found."], {}

    data["__date"] = data.iloc[:, idx_date].map(_date_to_iso)
    data = data[data["__date"].notna()].copy()
    if data.empty:
        return [], [f"Growth Report {filename}: no dated rows found."], {}

    # Validate payment columns before touching any data
    payments, unmapped = _payment_columns(colmap, data)
    if unmapped:
        return (
            [],
            [
                f"Import blocked. Unmapped payment type(s) found in Growth Report "
                f"{filename}: {', '.join(unmapped)}.\n"
                "Please add this payment type to the payment mapping before importing."
            ],
            {"unmapped_payment_types": unmapped},
        )

    # Locate the LAST occurrence of "service charge" in the header row so that
    # reports where the column appears twice (once as summary, once in the tax
    # breakdown) use the meaningful (non-zero) value.
    sc_col = _last_col_for(df, header_idx, "service charge")
    gst_sc_col = _last_col_for(df, header_idx, "gst on sevice charge") or _last_col_for(
        df, header_idx, "gst on service charge"
    )

    rows: List[Dict[str, Any]] = []
    for _, row in data.iterrows():
        out: Dict[str, Any] = {
            "date": row["__date"],
            "file_type": "growth_report_day_wise",
            "source_report": "growth_report_day_wise",
        }
        if location_id is not None:
            out["location_id"] = int(location_id)

        # Generic field extraction (skips fields handled manually below).
        # Several Petpooja headers have both long and short aliases in FIELD_MAP,
        # e.g. "net sales (₹)(m.a - d)" and "net sales".  The old loop allowed
        # a missing short alias to overwrite a correctly parsed long alias with
        # zero, which caused gross_total/net_total/my_amount/total_tax to save
        # as 0.  Keep the first parsed value unless a later alias has a real
        # non-zero value.
        for source, target in FIELD_MAP.items():
            if source in _MANUAL_FIELDS:
                continue
            val = round(_f(_value(row, colmap, source)), 2)
            if val != 0.0 or target not in out:
                out[target] = val

        # order_count and covers (covers defaults to order_count if no Pax column)
        out["order_count"] = _i(_value(row, colmap, "orders"))
        if "covers" not in out or out.get("covers", 0) == 0:
            out["covers"] = out["order_count"]

        # Service charge — use last-occurrence column to handle duplicate headers
        if sc_col is not None and sc_col < len(row):
            sc_val = _f(row.iloc[sc_col])
        else:
            sc_val = _f(_value(row, colmap, "service charge"))
        out["service_charge"] = round(sc_val, 2)

        # GST on service charge — same last-occurrence logic
        if gst_sc_col is not None and gst_sc_col < len(row):
            gst_sc_val = _f(row.iloc[gst_sc_col])
        else:
            gst_sc_val = _f(_value(row, colmap, "gst on sevice charge", "gst on service charge"))
        out["gst_on_service_charge"] = round(gst_sc_val, 2)

        # Initialise all payment fields to zero before accumulation
        for db_field in (
            "cash_sales",
            "card_sales",
            "due_payment_sales",
            "wallet_sales",
            "upi_sales",
            "gpay_sales",
            "bank_transfer_sales",
            "boh_sales",
        ):
            out[db_field] = 0.0

        # Accumulate payment columns (multiple headers may map to the same DB field)
        for header, idx in payments.items():
            db_field = ALLOWED_PAYMENT_COLUMNS[header]
            if idx < len(row):
                out[db_field] = round(float(out.get(db_field, 0) or 0) + _f(row.iloc[idx]), 2)

        rows.append(out)

    period_start, period_end = _extract_period(df)
    meta: Dict[str, Any] = {
        "period_start": period_start,
        "period_end": period_end,
        "row_count": len(rows),
    }
    return rows, [], meta
