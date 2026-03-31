"""
Parse Petpooja Restaurant Timing Report.

Extracts Breakfast / Lunch / Dinner revenue and order counts,
which are more accurate than timestamp-based guessing from the Item Report.

Expected structure (approximate):
  Row 0:  Name: Restaurant Timing Report
  Row 1:  Restaurant Name: Boteco
  Row 2:  Restaurant Address: ...
  Row N:  Timings | Total No. of Orders | ... | Total Amount ...
  Row N+1: Breakfast [08:00 - 11:30] | ...
  Row N+2: Lunch [12:00 - 17:30] | ...
  Row N+3: Dinner [18:00 - 24:00] | ...
  Row N+4: Whole Day [00:00 - 24:00] | ...
"""

from __future__ import annotations

import re
from io import BytesIO
from typing import Any, Dict, List, Optional

import pandas as pd


# -- Helpers -------------------------------------------------------------


def _f(val: Any) -> float:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return 0.0
    s = str(val).replace(",", "").replace("\u20b9", "").replace("Γé╣", "").strip()
    if not s or s.lower() == "nan":
        return 0.0
    try:
        return float(s)
    except ValueError:
        return 0.0


def _norm(s: Any) -> str:
    if s is None or (isinstance(s, float) and pd.isna(s)):
        return ""
    return re.sub(r"\s+", " ", str(s).strip().lower())


def _load_df(file_content: bytes) -> Optional[pd.DataFrame]:
    """Load the first sheet without a header row."""
    bio = BytesIO(file_content)
    for engine in (None, "openpyxl", "xlrd"):
        try:
            bio.seek(0)
            kw = {"engine": engine} if engine else {}
            return pd.read_excel(bio, sheet_name=0, header=None, **kw)
        except Exception:
            continue
    return None


def _extract_date_from_header(df: pd.DataFrame) -> Optional[str]:
    """Look for a date value in the first 8 rows."""
    import dateutil.parser as dparser  # type: ignore

    for i in range(min(8, len(df))):
        for j, v in enumerate(df.iloc[i].values):
            s = _norm(v)
            # If a cell says "date" look at the next cell for the value
            if s in ("date", "date :") or s.startswith("date"):
                tail = re.sub(r"^date\s*:?\s*", "", s).strip()
                # Try the remainder of this cell
                if tail:
                    try:
                        return dparser.parse(tail, dayfirst=True).strftime("%Y-%m-%d")
                    except Exception:
                        pass
                # Try the next cell in the same row
                if j + 1 < len(df.columns):
                    nxt = str(df.iloc[i, j + 1]).strip()
                    if nxt and nxt.lower() not in ("nan", ""):
                        try:
                            return dparser.parse(nxt, dayfirst=True).strftime(
                                "%Y-%m-%d"
                            )
                        except Exception:
                            pass
            # Otherwise try to parse the cell itself as a date
            # (avoid accidentally parsing integers like row counts)
            raw = str(v).strip()
            if (
                len(raw) >= 8
                and not raw.replace(".", "").replace("-", "").replace("/", "").isdigit()
            ):
                try:
                    ts = pd.to_datetime(raw, dayfirst=True, errors="coerce")
                    if pd.notna(ts) and ts.year > 2000:
                        return ts.strftime("%Y-%m-%d")
                except Exception:
                    pass
    return None


def _extract_date_from_filename(filename: str) -> Optional[str]:
    """
    Try to infer a report date from a filename like:
    Restaurant_Timing_Report_2026_03_30_09_44_26.xlsx
    If the download hour is before 14:00 we assume it's the previous day's report.
    """
    m = re.search(r"(\d{4})_(\d{2})_(\d{2})_(\d{2})_\d{2}_\d{2}", filename)
    if not m:
        return None
    from datetime import datetime, timedelta

    year, month, day, hour = (
        int(m.group(1)),
        int(m.group(2)),
        int(m.group(3)),
        int(m.group(4)),
    )
    try:
        dt = datetime(year, month, day)
        if hour < 14:
            dt -= timedelta(days=1)
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        return None


def _find_header_row(df: pd.DataFrame) -> Optional[int]:
    """Find the row containing the column headers (Timings / Total No. of Orders)."""
    for i in range(min(20, len(df))):
        parts = [_norm(x) for x in df.iloc[i].values if _norm(x)]
        joined = " ".join(parts)
        if "timing" in joined and (
            "order" in joined or "dine in" in joined or "amount" in joined
        ):
            return i
    return None


def _extract_restaurant_name(df: pd.DataFrame) -> Optional[str]:
    for i in range(min(5, len(df))):
        for j, v in enumerate(df.iloc[i].values):
            s = _norm(v)
            if "restaurant name" in s:
                # Value after colon in same cell
                after = re.sub(r"restaurant name\s*:?\s*", "", s).strip()
                if after:
                    return after.title()
                # Value in next cell
                if j + 1 < len(df.columns):
                    nxt = str(df.iloc[i, j + 1]).strip()
                    if nxt and nxt.lower() not in ("nan", ""):
                        return nxt
    return None


# -- Public API ----------------------------------------------------------


def parse_timing_report(file_content: bytes, filename: str) -> Optional[Dict[str, Any]]:
    """
    Parse a Petpooja Restaurant Timing Report.

    Returns a dict:
      {
        "date": "YYYY-MM-DD" | None,
        "restaurant_name": str | None,
        "services": [{"type": "Breakfast"|"Lunch"|"Dinner", "amount": float, "orders": int}, ...],
        "whole_day_total": float,
        "file_type": "timing_report",
        "filename": str,
      }

    Returns None if the file doesn't look like a timing report.
    """
    df = _load_df(file_content)
    if df is None or df.empty:
        return None

    date = _extract_date_from_header(df)
    if date is None:
        date = _extract_date_from_filename(filename)

    restaurant = _extract_restaurant_name(df)
    header_idx = _find_header_row(df)

    if header_idx is None:
        return None

    # Build column → index map from the header row
    colmap: Dict[str, int] = {}
    for j, v in enumerate(df.iloc[header_idx].values):
        k = _norm(v)
        if k:
            colmap[k] = j

    # Identify the amount column to use
    # Preference order: "total amount" > "dine in total" > anything with "amount"
    idx_amount: Optional[int] = None
    idx_orders: Optional[int] = None

    for k, j in colmap.items():
        if "total no" in k and "order" in k:
            idx_orders = j
        if idx_amount is None:
            if k == "total amount" or "total amount" in k:
                idx_amount = j
        if idx_amount is None:
            if "dine in" in k and ("total" in k or "amount" in k):
                idx_amount = j

    # Broader fallback: first column containing "amount"
    if idx_amount is None:
        for k, j in colmap.items():
            if "amount" in k:
                idx_amount = j
                break

    if idx_amount is None:
        return None

    # Meal period keywords → canonical service names
    meal_map = {
        "breakfast": "Breakfast",
        "lunch": "Lunch",
        "dinner": "Dinner",
    }

    services: List[Dict[str, Any]] = []
    whole_day_total = 0.0

    for ri in range(header_idx + 1, min(header_idx + 15, len(df))):
        label = _norm(df.iloc[ri].iloc[0]) if len(df.columns) > 0 else ""
        if not label:
            continue
        amount = (
            _f(df.iloc[ri].iloc[idx_amount]) if idx_amount < len(df.columns) else 0.0
        )
        orders = (
            int(_f(df.iloc[ri].iloc[idx_orders]))
            if idx_orders is not None and idx_orders < len(df.columns)
            else 0
        )

        if "whole day" in label or label == "total":
            whole_day_total = amount
            continue

        for key, service_name in meal_map.items():
            if key in label:
                if amount > 0 or orders > 0:
                    services.append(
                        {
                            "type": service_name,
                            "amount": amount,
                            "orders": orders,
                        }
                    )
                break

    # Only return a result if we found something useful
    if not services and whole_day_total <= 0:
        return None

    return {
        "date": date,
        "restaurant_name": restaurant,
        "services": services,
        "whole_day_total": whole_day_total,
        "file_type": "timing_report",
        "filename": filename,
    }
