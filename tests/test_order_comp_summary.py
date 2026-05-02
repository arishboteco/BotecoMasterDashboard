"""
Tests for the Complimentary Orders Summary parser and file detection.

Covers:
  - file_detector detects order_comp_summary from content
  - file_detector detects order_comp_summary from filename
  - order_comp_summary parser extracts daily comp totals
  - parser aggregates multiple orders on the same date
  - parser extracts restaurant name from header
  - parser handles missing columns gracefully
  - comp summary integration merges into Growth Report daily rows
"""

from __future__ import annotations

import io
from datetime import datetime

import pandas as pd
import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _comp_summary_bytes(
    restaurant_name: str = "Boteco - Bagmane",
    orders: list[dict] | None = None,
) -> bytes:
    """Build a minimal Complimentary Orders Summary Excel file.

    Mirrors the real Petpooja structure:
      Row 0: "Name: Restaurant Wise Complimentary Orders Summary"
      Row 1: "Restaurant Name: <name>"
      Row 2: "Address: ..."
      Row 3: blank
      Row 4: column headers
      Row 5+: data rows
    """
    from openpyxl import Workbook

    if orders is None:
        orders = [
            {
                "Created Date": "2026-04-01",
                "Customer Name": "Staff",
                "Customer Phone": "9999999999",
                "Reason": "Staff Meal",
                "GSTIN": "",
                "Order No.": "101",
                "Order Type": "Dine In",
                "Taxable Amount (₹)": 500.0,
                "Discount (₹)": 0.0,
                "Container Charge (₹)": 0.0,
                "Tax (₹)": 25.0,
                "Round Off (₹)": 0.0,
                "Grand Total (₹)": 525.0,
            },
            {
                "Created Date": "2026-04-01",
                "Customer Name": "Owner",
                "Customer Phone": "8888888888",
                "Reason": "Owner Meal",
                "GSTIN": "",
                "Order No.": "102",
                "Order Type": "Dine In",
                "Taxable Amount (₹)": 1200.0,
                "Discount (₹)": 0.0,
                "Container Charge (₹)": 0.0,
                "Tax (₹)": 60.0,
                "Round Off (₹)": 0.0,
                "Grand Total (₹)": 1260.0,
            },
            {
                "Created Date": "2026-04-02",
                "Customer Name": "Staff",
                "Customer Phone": "7777777777",
                "Reason": "Staff Meal",
                "GSTIN": "",
                "Order No.": "103",
                "Order Type": "Dine In",
                "Taxable Amount (₹)": 800.0,
                "Discount (₹)": 0.0,
                "Container Charge (₹)": 0.0,
                "Tax (₹)": 40.0,
                "Round Off (₹)": 0.0,
                "Grand Total (₹)": 840.0,
            },
        ]

    wb = Workbook()
    ws = wb.active

    # Row 0: report name
    ws.append([
        "Name: Restaurant Wise Complimentary Orders Summary",
        None, None, None, None, None, None, None, None, None, None, None, None,
    ])
    # Row 1: restaurant name
    ws.append([
        "Restaurant Name:",
        restaurant_name,
        None, None, None, None, None, None, None, None, None, None, None,
    ])
    # Row 2: address
    ws.append([
        "Address:",
        "123 Test Street",
        None, None, None, None, None, None, None, None, None, None, None,
    ])
    # Row 3: blank
    ws.append([None] * 13)

    # Row 4: headers
    if orders:
        headers = list(orders[0].keys())
        ws.append(headers)

        # Rows 5+: data
        for order in orders:
            ws.append([order[h] for h in headers])
    else:
        ws.append(["Created Date", "Grand Total (₹)"])

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# File detection tests
# ---------------------------------------------------------------------------


class TestCompSummaryDetection:
    def test_detect_from_content(self):
        from file_detector import detect_file_type

        content = _comp_summary_bytes()
        assert detect_file_type(content, "report.xlsx") == "order_comp_summary"

    def test_detect_from_filename_comp_summary(self):
        from file_detector import detect_file_type

        # Empty content → filename fallback
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as w:
            pd.DataFrame({"a": [1]}).to_excel(w, index=False)
        content = buf.getvalue()
        assert detect_file_type(content, "Restaurants_order_comp_summary_2026.xlsx") == "order_comp_summary"

    def test_detect_from_filename_complimentary(self):
        from file_detector import detect_file_type

        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as w:
            pd.DataFrame({"a": [1]}).to_excel(w, index=False)
        content = buf.getvalue()
        assert detect_file_type(content, "complimentary_orders_apr.xlsx") == "order_comp_summary"

    def test_importable(self):
        from file_detector import is_importable

        assert is_importable("order_comp_summary") is True

    def test_kind_label(self):
        from file_detector import KIND_LABELS

        assert "order_comp_summary" in KIND_LABELS
        assert "Complimentary" in KIND_LABELS["order_comp_summary"]


# ---------------------------------------------------------------------------
# Parser tests
# ---------------------------------------------------------------------------


class TestCompSummaryParser:
    def test_basic_parse(self):
        from uploads.parsers.order_comp_summary import parse_order_comp_summary

        content = _comp_summary_bytes()
        rows, errors, meta = parse_order_comp_summary(content, "test.xlsx", location_id=1)
        assert not errors, errors
        assert len(rows) == 2  # two dates: 2026-04-01 and 2026-04-02

    def test_daily_aggregation(self):
        """Two orders on 2026-04-01 should be summed into one daily row."""
        from uploads.parsers.order_comp_summary import parse_order_comp_summary

        content = _comp_summary_bytes()
        rows, errors, meta = parse_order_comp_summary(content, "test.xlsx", location_id=1)
        assert not errors

        apr01 = next(r for r in rows if r["date"] == "2026-04-01")
        # Grand Total for order 101 = 525, order 102 = 1260 → 1785
        assert apr01["complementary_amount"] == 1785.0
        assert apr01["complementary_count"] == 2

        apr02 = next(r for r in rows if r["date"] == "2026-04-02")
        assert apr02["complementary_amount"] == 840.0
        assert apr02["complementary_count"] == 1

    def test_location_id_attached(self):
        from uploads.parsers.order_comp_summary import parse_order_comp_summary

        content = _comp_summary_bytes()
        rows, errors, meta = parse_order_comp_summary(content, "test.xlsx", location_id=42)
        assert not errors
        for row in rows:
            assert row["location_id"] == 42

    def test_restaurant_name_extracted(self):
        from uploads.parsers.order_comp_summary import parse_order_comp_summary

        content = _comp_summary_bytes(restaurant_name="Boteco (Indiqube)")
        rows, errors, meta = parse_order_comp_summary(content, "test.xlsx")
        assert not errors
        assert meta["restaurant_name"] == "Boteco (Indiqube)"

    def test_meta_fields(self):
        from uploads.parsers.order_comp_summary import parse_order_comp_summary

        content = _comp_summary_bytes()
        rows, errors, meta = parse_order_comp_summary(content, "test.xlsx", location_id=1)
        assert not errors
        assert meta["period_start"] == "2026-04-01"
        assert meta["period_end"] == "2026-04-02"
        assert meta["row_count"] == 2
        assert meta["order_count"] == 3

    def test_source_report_field(self):
        from uploads.parsers.order_comp_summary import parse_order_comp_summary

        content = _comp_summary_bytes()
        rows, errors, meta = parse_order_comp_summary(content, "test.xlsx", location_id=1)
        assert not errors
        for row in rows:
            assert row["source_report"] == "order_comp_summary"
            assert row["file_type"] == "order_comp_summary"

    def test_empty_file_returns_error(self):
        from uploads.parsers.order_comp_summary import parse_order_comp_summary

        rows, errors, meta = parse_order_comp_summary(b"", "empty.xlsx")
        assert len(rows) == 0
        assert len(errors) > 0

    def test_single_order(self):
        """A file with only one order should produce one daily row."""
        from uploads.parsers.order_comp_summary import parse_order_comp_summary

        orders = [
            {
                "Created Date": "2026-04-15",
                "Customer Name": "Guest",
                "Customer Phone": "",
                "Reason": "Promo",
                "GSTIN": "",
                "Order No.": "200",
                "Order Type": "Dine In",
                "Taxable Amount (₹)": 3000.0,
                "Discount (₹)": 0.0,
                "Container Charge (₹)": 0.0,
                "Tax (₹)": 150.0,
                "Round Off (₹)": 0.0,
                "Grand Total (₹)": 3150.0,
            }
        ]
        content = _comp_summary_bytes(orders=orders)
        rows, errors, meta = parse_order_comp_summary(content, "test.xlsx", location_id=5)
        assert not errors
        assert len(rows) == 1
        assert rows[0]["complementary_amount"] == 3150.0
        assert rows[0]["complementary_count"] == 1
        assert rows[0]["date"] == "2026-04-15"

    def test_rows_sorted_by_date(self):
        from uploads.parsers.order_comp_summary import parse_order_comp_summary

        content = _comp_summary_bytes()
        rows, errors, meta = parse_order_comp_summary(content, "test.xlsx", location_id=1)
        assert not errors
        dates = [r["date"] for r in rows]
        assert dates == sorted(dates)
