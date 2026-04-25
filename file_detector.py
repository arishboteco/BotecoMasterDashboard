"""
Auto-detect Petpooja export file types from CONTENT (not filename).

Detects:
  dynamic_report       - Dynamic Report CSV (per-bill order-level) [PRIMARY]
  item_order_details   - Item Report With Customer/Order Details (.xlsx)
  customer_report      - Customer/Booking report (.xlsx)
  timing_report        - Restaurant Timing Report (.xlsx)
  order_summary_csv    - Order Summary Report (.csv)
  flash_report         - POS Collection / Flash Report (.xlsx)
  group_wise           - Item Report Group Wise (.xlsx)
  all_restaurant       - All Restaurant Sales Report (.xlsx)
  comparison           - Restaurant Wise Comparison Report (.xls / HTML)
  unknown              - Unrecognised file
"""

from __future__ import annotations

import re
from io import BytesIO
from typing import Tuple

import pandas as pd
import boteco_logger

logger = boteco_logger.get_logger(__name__)


# -- Priority: which types contribute new importable data ----------------

IMPORT_PRIORITY = {
    "dynamic_report": 0,
    "item_order_details": 1,
    "timing_report": 2,
    "flash_report": 3,
    "order_summary_csv": 4,
}

SKIP_TYPES = {
    "customer_report",
    "group_wise",
    "all_restaurant",
    "comparison",
    "unknown",
}

KIND_LABELS = {
    "dynamic_report": "Dynamic Report (per-bill CSV — primary data source)",
    "item_order_details": "Item Report (line-item sales — primary data source)",
    "customer_report": "Customer Report (detected but not imported)",
    "timing_report": "Timing Report (breakfast/lunch/dinner revenue breakdown)",
    "order_summary_csv": "Order Summary CSV (per-order totals)",
    "flash_report": "Flash Report (single-day POS summary)",
    "group_wise": "Group Wise Report (category summary — redundant with Item Report)",
    "all_restaurant": "All Restaurant Sales (outlet summary)",
    "comparison": "Restaurant Comparison (multi-outlet overview)",
    "unknown": "Unrecognised file format",
}


def is_importable(kind: str) -> bool:
    return kind in IMPORT_PRIORITY


def is_skippable(kind: str) -> bool:
    return kind in SKIP_TYPES


# -- Internal helpers ----------------------------------------------------


def _norm(s) -> str:
    """Normalise a cell value to lowercase stripped string."""
    if s is None or (isinstance(s, float) and pd.isna(s)):
        return ""
    return re.sub(r"\s+", " ", str(s).strip().lower())


def _peek_text(file_content: bytes, filename: str) -> str:
    """Extract a flat text blob from the first ~12 rows of any supported file."""
    tokens: list = []
    bio = BytesIO(file_content)
    low = filename.lower()

    # CSV files
    if low.endswith(".csv"):
        try:
            bio.seek(0)
            df = pd.read_csv(bio, nrows=5)
            tokens.extend(_norm(c) for c in df.columns)
            for i in range(min(5, len(df))):
                tokens.extend(_norm(v) for v in df.iloc[i].values)
        except (pd.errors.EmptyDataError, pd.errors.ParserError, UnicodeDecodeError, ValueError) as ex:
            logger.warning(
                "CSV peek failed in file_detector.py file=%s error=%s",
                filename,
                ex,
            )
        return " ".join(t for t in tokens if t)

    # HTML-disguised .xls files
    head = file_content[:2500].lower()
    if b"<html" in head or b"<!doctype" in head:
        try:
            bio.seek(0)
            dfs = pd.read_html(bio)
            for d in dfs[:2]:
                for i in range(min(8, len(d))):
                    tokens.extend(_norm(v) for v in d.iloc[i].values)
        except (ValueError, ImportError, TypeError) as ex:
            logger.warning(
                "HTML/XLS peek failed in file_detector.py file=%s error=%s",
                filename,
                ex,
            )
        return " ".join(t for t in tokens if t)

    # Excel files (.xlsx / .xls)
    for engine in (None, "openpyxl", "xlrd"):
        try:
            bio.seek(0)
            kw = {"engine": engine} if engine else {}
            df = pd.read_excel(bio, sheet_name=0, header=None, nrows=12, **kw)
            for i in range(min(12, len(df))):
                tokens.extend(_norm(v) for v in df.iloc[i].values)
            break
        except (
            ValueError,
            OSError,
            ImportError,
            KeyError,
            pd.errors.EmptyDataError,
            pd.errors.ParserError,
        ) as ex:
            logger.debug(
                "Excel peek attempt failed in file_detector.py file=%s engine=%s error=%s",
                filename,
                engine or "auto",
                ex,
            )
            continue

    return " ".join(t for t in tokens if t)


# -- Public API ----------------------------------------------------------


def detect_file_type(file_content: bytes, filename: str) -> str:
    """
    Inspect file content and return one of the type strings listed above.
    Detection is content-first; filename is a fallback only.
    """
    text = _peek_text(file_content, filename)
    if not text:
        return "unknown"

    # 1. Item Report With Customer/Order Details
    #    Has sub total + final total + invoice together
    if "sub total" in text and "final total" in text and "invoice" in text:
        return "item_order_details"

    # 2. Customer / booking report
    #    Has pax count, or booking + restaurant session, or Dineout-style columns
    if "pax count" in text or ("booking" in text and "restaurant session" in text):
        return "customer_report"
    # Dineout / EazyDiner style: booked for day + booking start time
    if "booked for" in text and ("booking" in text or "restaurant" in text):
        return "customer_report"

    # 3. Dynamic Report CSV (per-bill)
    #    Has bill no + pax + net amount + gross sale
    if (
        "bill no" in text
        and "pax" in text
        and "net amount" in text
        and "gross sale" in text
    ):
        return "dynamic_report"

    # 4. Restaurant Timing Report
    #    Breakfast + Lunch + Dinner + timing keyword
    if (
        "breakfast" in text
        and "lunch" in text
        and "dinner" in text
        and ("timing" in text or "dine in" in text)
    ):
        return "timing_report"

    # 4. Order Summary CSV
    #    Has restaurant_name + my_amount + kot_no (CSV order-level)
    if "restaurant_name" in text and "my_amount" in text and "kot_no" in text:
        return "order_summary_csv"

    # 5. Flash / POS Collection Report
    if "pos collection" in text or "sale per pax" in text:
        return "flash_report"

    # 6. Item Report Group Wise
    #    group name + net sales, but NOT sub total (which the Item Report has)
    if "group name" in text and "net sales" in text and "sub total" not in text:
        return "group_wise"

    # 7. Restaurant Wise Comparison
    if "outlet" in text and "statistics" in text:
        return "comparison"

    # 8. All Restaurant Sales Report
    if "restaurants" in text and "invoice nos" in text:
        return "all_restaurant"

    # Fallback: filename hints
    fn = filename.lower()
    if (
        "customerorder" in fn
        or "customer_order" in fn
        or "item_report_with_customer" in fn
    ):
        return "item_order_details"
    if "customer_report" in fn or "customerreport" in fn:
        return "customer_report"
    if "timing" in fn:
        return "timing_report"
    if "order_summary" in fn or "ordersummary" in fn:
        return "order_summary_csv"
    if "flash" in fn or "pos_collection" in fn:
        return "flash_report"
    if "group_wise" in fn or "groupwise" in fn:
        return "group_wise"
    if "comparison" in fn or "restaurant_wise" in fn:
        return "comparison"
    if "all_restaurant" in fn:
        return "all_restaurant"

    return "unknown"


def detect_and_describe(file_content: bytes, filename: str) -> Tuple[str, str]:
    """Return (type_key, human_readable_description)."""
    kind = detect_file_type(file_content, filename)
    return kind, KIND_LABELS.get(kind, "Unknown file type")
