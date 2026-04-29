from __future__ import annotations

import re
from datetime import datetime
from io import BytesIO
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd


ALLOWED_PAYMENT_COLUMNS = {
    "cash": "cash_sales",
    "card": "card_sales",
    "due payment": "due_payment_sales",
    "wallet": "wallet_sales",
    "upi": "upi_sales",
    "other [g pay]": "gpay_sales",
    "other [gpay]": "gpay_sales",
    "other [g pay]()": "gpay_sales",
    "other [g pay ]": "gpay_sales",
    "other [bank transfer]": "bank_transfer_sales",
    "other [boh]": "boh_sales",
}

IGNORED_ZERO_PAYMENT_COLUMNS = {
    "not paid",
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
    "amount (service charge)",
    "amount (gst on sevice charge)",
    "amount (gst on service charge)",
    "gst on sevice charge",
    "gst on service charge",
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
}

FIELD_MAP = {
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
    "service charge": "service_charge",
    "gst on sevice charge": "gst_on_service_charge",
    "gst on service charge": "gst_on_service_charge",
    "delivery": "delivery_sales",
    "pick up": "pickup_sales",
    "dine in": "dine_in_sales",
    "menu qr code": "menu_qr_sales",
    "expenses": "expenses",
}


def _norm(value: Any) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    s = str(value).replace("\xa0", " ").strip().lower()
    s = re.sub(r"\s+", " ", s)
    s = s.replace("g pay", "g pay")
    return s


def _clean_payment_header(value: Any) -> str:
    s = _norm(value)
    s = re.sub(r"\[\s*", "[", s)
    s = re.sub(r"\s*\]", "]", s)
    s = re.sub(r"\s+", " ", s)
    if s == "other [g pay]" or s == "other [g pay]()":
        return "other [g pay]"
    return s


def _f(value: Any) -> float:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return 0.0
    text = str(value).replace(",", "").replace("₹", "").replace("Γé╣", "").strip()
    if not text or text.lower() in {"nan", "none"}:
        return 0.0
    try:
        return float(text)
    except ValueError:
        return 0.0


def _i(value: Any) -> int:
    return int(round(_f(value)))


def _date_to_iso(value: Any) -> Optional[str]:
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
    for i in range(min(40, len(df))):
        joined = " ".join(_norm(v) for v in df.iloc[i].values if _norm(v))
        if "net sales" in joined and "total tax" in joined and "cash" in joined and "card" in joined:
            return i
    return None


def _header_map(df: pd.DataFrame, header_idx: int) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for i, value in enumerate(df.iloc[header_idx].values):
        key = _clean_payment_header(value)
        if key and key not in out:
            out[key] = i
    return out


def _payment_columns(colmap: Dict[str, int], data: pd.DataFrame) -> Tuple[Dict[str, int], List[str]]:
    payments: Dict[str, int] = {}
    unmapped: List[str] = []
    for header, idx in colmap.items():
        if header in ALLOWED_PAYMENT_COLUMNS:
            payments[header] = idx
            continue
        if header.startswith("other [") or header in {"cash", "card", "due payment", "wallet", "upi", "not paid"}:
            if header in IGNORED_ZERO_PAYMENT_COLUMNS:
                total = float(data.iloc[:, idx].map(_f).sum()) if idx < data.shape[1] else 0.0
                if abs(total) > 0.005:
                    unmapped.append(header)
            elif header not in BASE_FIELDS:
                total = float(data.iloc[:, idx].map(_f).sum()) if idx < data.shape[1] else 0.0
                if abs(total) > 0.005:
                    unmapped.append(header)
    return payments, sorted(set(unmapped))


def _value(row: pd.Series, colmap: Dict[str, int], *names: str) -> Any:
    for name in names:
        idx = colmap.get(name)
        if idx is not None and idx < len(row):
            return row.iloc[idx]
    return 0


def _extract_period(df: pd.DataFrame) -> Tuple[Optional[str], Optional[str]]:
    if df.empty:
        return None, None
    for i in range(min(10, len(df))):
        values = [str(v) for v in df.iloc[i].values if str(v).strip().lower() not in {"nan", "none", ""}]
        joined = " ".join(values)
        match = re.search(r"(\d{4}-\d{2}-\d{2})\s+to\s+(\d{4}-\d{2}-\d{2})", joined)
        if match:
            return match.group(1), match.group(2)
    return None, None


def parse_growth_report_day_wise(
    file_content: bytes,
    filename: str,
    location_id: Optional[int] = None,
) -> Tuple[List[Dict[str, Any]], List[str], Dict[str, Any]]:
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
    payments, unmapped = _payment_columns(colmap, data)
    if unmapped:
        return [], [
            "Import blocked. Unmapped payment type(s) in Growth Report "
            f"{filename}: {', '.join(unmapped)}"
        ], {"unmapped_payment_types": unmapped}
    rows: List[Dict[str, Any]] = []
    for _, row in data.iterrows():
        out: Dict[str, Any] = {
            "date": row["__date"],
            "file_type": "growth_report_day_wise",
            "source_report": "growth_report_day_wise",
        }
        if location_id is not None:
            out["location_id"] = int(location_id)
        for source, target in FIELD_MAP.items():
            if source in {"service charge"}:
                continue
            out[target] = round(_f(_value(row, colmap, source)), 2)
        out["order_count"] = _i(_value(row, colmap, "orders"))
        out["covers"] = out["order_count"]
        out["service_charge"] = round(
            _f(_value(row, colmap, "service charge"))
            or _f(_value(row, colmap, "amount (service charge)")),
            2,
        )
        out["gst_on_service_charge"] = round(
            _f(_value(row, colmap, "gst on sevice charge", "gst on service charge")), 2
        )
        for db_field in {
            "cash_sales",
            "card_sales",
            "due_payment_sales",
            "wallet_sales",
            "upi_sales",
            "gpay_sales",
            "bank_transfer_sales",
            "boh_sales",
        }:
            out[db_field] = 0.0
        for header, idx in payments.items():
            db_field = ALLOWED_PAYMENT_COLUMNS[header]
            out[db_field] = round(float(out.get(db_field, 0) or 0) + _f(row.iloc[idx]), 2)
        rows.append(out)
    period_start, period_end = _extract_period(df)
    meta = {"period_start": period_start, "period_end": period_end, "row_count": len(rows)}
    return rows, [], meta
