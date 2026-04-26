"""Order Summary CSV parser extracted from smart_upload."""

from __future__ import annotations

from io import BytesIO
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

import pos_parser

PARSE_EXCEPTIONS = (
    ValueError,
    TypeError,
    KeyError,
    OSError,
    UnicodeDecodeError,
    pd.errors.ParserError,
    pd.errors.EmptyDataError,
)

SUCCESS_STATUSES = {"", "success", "successorder"}


def _normalize_status_token(value: Any) -> str:
    """Normalize status text for robust comparisons across export variants."""
    token = str(value or "").strip().lower()
    return token.replace(" ", "").replace("_", "").replace("-", "")


def _is_success_order_status(raw_status: str) -> bool:
    """Return True for accepted success statuses from Order Summary exports."""
    if "complimentary" in raw_status:
        return False
    return _normalize_status_token(raw_status) in SUCCESS_STATUSES


def parse_order_summary_csv(
    content: bytes,
    filename: str,
) -> Tuple[Optional[List[Dict[str, Any]]], List[str]]:
    """Parse Order Summary CSV (order-level rows) into per-day records."""
    notes: List[str] = []
    try:
        df = pd.read_csv(BytesIO(content))
    except PARSE_EXCEPTIONS as ex:
        return None, [f"Could not read CSV: {ex}"]

    df.columns = [c.strip() for c in df.columns]
    col_lower = {c.lower(): c for c in df.columns}

    def _get_col(*names: str) -> Optional[str]:
        for n in names:
            if n in col_lower:
                return col_lower[n]
        return None

    date_col = _get_col("date")
    amount_col = _get_col("my_amount", "amount")
    status_col = _get_col("status")
    pay_col = _get_col("payment_type", "payment type")

    if not date_col or not amount_col:
        return None, ["Order Summary CSV missing required columns (date / my_amount)."]

    date_tokens = df[date_col].astype(str).str.slice(0, 10).str.strip()
    parsed_ts = pd.to_datetime(date_tokens, errors="coerce")
    parsed_dates = parsed_ts.dt.strftime("%Y-%m-%d")
    fallback_mask = parsed_dates.isna()
    if fallback_mask.any():
        parsed_dates.loc[fallback_mask] = date_tokens.loc[fallback_mask].map(pos_parser.parse_date)

    success_mask = pd.Series(True, index=df.index)
    if status_col:
        status_norm = df[status_col].fillna("").astype(str).str.strip().str.lower()
        success_mask = status_norm.map(_is_success_order_status)

    amount_vals = pd.to_numeric(
        df[amount_col].fillna("").astype(str).str.replace(",", "", regex=False),
        errors="coerce",
    ).fillna(0.0)

    work_df = pd.DataFrame(
        {
            "day": parsed_dates,
            "amount": amount_vals,
        },
        index=df.index,
    )
    work_df = work_df[work_df["day"].notna() & success_mask]

    if pay_col:
        work_df["bucket"] = (
            df.loc[work_df.index, pay_col].fillna("").astype(str).map(pos_parser.payment_bucket)
        )
        work_df["bucket"] = work_df["bucket"].where(
            work_df["bucket"].isin(("cash", "card", "gpay", "zomato")),
            "other",
        )
    else:
        work_df["bucket"] = "other"

    days: Dict[str, Dict[str, Any]] = {}
    if not work_df.empty:
        day_totals = work_df.groupby("day", sort=True)["amount"].sum()
        day_bucket = (
            work_df.groupby(["day", "bucket"], sort=True)["amount"].sum().unstack(fill_value=0.0)
        )
        for day, net_total in day_totals.items():
            days[day] = {
                "net": float(net_total),
                "gross": float(net_total),
                "tax": 0.0,
                "cash": float(day_bucket.at[day, "cash"]) if "cash" in day_bucket.columns else 0.0,
                "card": float(day_bucket.at[day, "card"]) if "card" in day_bucket.columns else 0.0,
                "gpay": float(day_bucket.at[day, "gpay"]) if "gpay" in day_bucket.columns else 0.0,
                "zomato": float(day_bucket.at[day, "zomato"])
                if "zomato" in day_bucket.columns
                else 0.0,
                "other": float(day_bucket.at[day, "other"])
                if "other" in day_bucket.columns
                else 0.0,
                "discount": 0.0,
                "service_charge": 0.0,
                "covers": 0,
            }

    out: List[Dict[str, Any]] = []
    for d in sorted(days.keys()):
        b = days[d]
        if b["net"] <= 0:
            continue
        out.append(
            {
                "date": d,
                "filename": filename,
                "file_type": "order_summary_csv",
                "gross_total": b["gross"],
                "net_total": b["net"],
                "cash_sales": b["cash"],
                "card_sales": b["card"],
                "gpay_sales": b["gpay"],
                "zomato_sales": b["zomato"],
                "other_sales": b["other"],
                "discount": b["discount"],
                "complimentary": 0.0,
                "cgst": 0.0,
                "sgst": 0.0,
                "service_charge": b["service_charge"],
                "covers": b["covers"],
                "categories": [],
                "services": [],
            }
        )

    return (out if out else None), notes
