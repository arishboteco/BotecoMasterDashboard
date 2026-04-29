"""
Strict payment column normalisation for the Growth Report import flow.

Exposes two public functions:
  normalize_payment_column(raw_name)  → canonical DB field name or None
  validate_payment_columns_or_raise(columns, dataframe)  → raises ValueError on problems
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional

import pandas as pd

# ---------------------------------------------------------------------------
# Canonical payment field names (DB column names in daily_summary)
# ---------------------------------------------------------------------------

CANONICAL_PAYMENT_FIELDS = {
    "cash_sales",
    "card_sales",
    "due_payment_sales",
    "wallet_sales",
    "upi_sales",
    "gpay_sales",
    "bank_transfer_sales",
    "boh_sales",
}

# Mapping from normalised raw header → DB field
_ALLOWED: Dict[str, str] = {
    "cash": "cash_sales",
    "card": "card_sales",
    "due payment": "due_payment_sales",
    "not paid": "due_payment_sales",  # older Petpooja label for same concept
    "wallet": "wallet_sales",
    "upi": "upi_sales",
    "other [g pay]": "gpay_sales",
    "other [gpay]": "gpay_sales",
    "other [g pay]()": "gpay_sales",
    "other [bank transfer]": "bank_transfer_sales",
    "other [boh]": "boh_sales",
}

# These are allowed to appear with zero value; non-zero blocks the import.
_IGNORED_IF_ZERO = {
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


def _norm(raw: str) -> str:
    s = re.sub(r"\s+", " ", raw.replace("\xa0", " ").strip().lower())
    # Collapse whitespace inside brackets
    s = re.sub(r"\[\s+", "[", s)
    s = re.sub(r"\s+\]", "]", s)
    s = re.sub(r"\s+", " ", s)
    if s.endswith("()"):
        s = s[:-2].rstrip()
    return s


def normalize_payment_column(raw_name: str) -> Optional[str]:
    """Map a raw column header to its canonical DB field name.

    Returns None if the column is not a payment column or is in the
    ignored-if-zero set (those are structural / online columns).
    """
    key = _norm(raw_name)
    return _ALLOWED.get(key)


def _col_total(df: pd.DataFrame, col_name: str) -> float:
    """Sum a named DataFrame column, treating non-numeric as 0."""
    if col_name not in df.columns:
        return 0.0
    return float(
        df[col_name]
        .map(
            lambda v: 0.0
            if (v is None or (isinstance(v, float) and pd.isna(v)))
            else _to_float(v)
        )
        .sum()
    )


def _to_float(value: object) -> float:
    try:
        return float(
            str(value).replace(",", "").replace("₹", "").strip()
        )
    except (ValueError, TypeError):
        return 0.0


def validate_payment_columns_or_raise(
    columns: List[str],
    dataframe: pd.DataFrame,
) -> None:
    """Raise ValueError if any unknown payment column has non-zero total values.

    Args:
        columns:   List of raw column header strings from the file.
        dataframe: The data rows (used to check column totals).

    Raises:
        ValueError with a user-readable message listing the problem columns.
    """
    problems: List[str] = []
    for raw in columns:
        key = _norm(raw)
        if key in _ALLOWED:
            continue  # known and mapped
        if key in _IGNORED_IF_ZERO:
            total = _col_total(dataframe, raw)
            if abs(total) > 0.005:
                problems.append(
                    f"Other [{raw}] is marked as zero-only but has value {total:.2f}"
                )
            continue
        # For anything else that looks payment-shaped, check if it has value
        is_payment_shaped = key.startswith("other [") or key in {
            "cash",
            "card",
            "due payment",
            "not paid",
            "wallet",
            "upi",
        }
        if not is_payment_shaped:
            continue
        total = _col_total(dataframe, raw)
        if abs(total) > 0.005:
            problems.append(f"Unmapped payment type: {raw} (total {total:.2f})")

    if problems:
        detail = "\n  ".join(problems)
        raise ValueError(
            f"Import blocked. Unmapped payment type found:\n  {detail}\n"
            "Please add this payment type to the payment mapping before importing."
        )
