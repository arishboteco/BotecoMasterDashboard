"""
Tests for the Growth Report + Item Report import flow.

Covers:
  - file_detector detects growth_report_day_wise
  - file_detector detects item_order_details
  - location detection: exact match rules
  - payment mapping service
  - growth report parser produces daily_summary-shaped rows
  - item category parser produces category_summary-shaped rows
  - database_writes build_daily_summary_row_new_flow includes all new fields
"""

from __future__ import annotations

import io

import pandas as pd
import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_excel_bytes(data: dict, extra_header_rows: int = 0) -> bytes:
    """Build a minimal in-memory Excel file with optional title rows before header."""
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df = pd.DataFrame(data)
        # Write title rows first if requested
        startrow = extra_header_rows
        df.to_excel(writer, index=False, startrow=startrow)
    return buf.getvalue()


def _growth_report_bytes(
    restaurant_name: str = "Boteco",
    payment_cols: dict | None = None,
    extra_cols: dict | None = None,
    rupee_headers: bool = False,
) -> bytes:
    """Build a minimal Growth Report Excel that the parser can read.

    When rupee_headers=True, uses Petpooja's real ₹-symbol column headers
    (e.g. "Net Sales (₹)(M.A - D)") instead of the short forms.
    """
    rows = [
        # Row 0: date filter
        {"Date": "Date:", "Orders": "2026-04-01 to 2026-04-01",
         "Net Sales": None, "Total Tax": None, "Cash": None, "Card": None,
         "UPI": None, "My Amount": None, "Discount": None,
         "Service Charge": None, "CGST": None, "SGST": None,
         "Gst on sevice charge": None, "Round Off": None, "Total": None,
         "Expenses": None, "Due Payment": None},
        # Row 1: name
        {"Date": "Name:", "Orders": "Growth Report: Day Wise",
         "Net Sales": None, "Total Tax": None, "Cash": None, "Card": None,
         "UPI": None, "My Amount": None, "Discount": None,
         "Service Charge": None, "CGST": None, "SGST": None,
         "Gst on sevice charge": None, "Round Off": None, "Total": None,
         "Expenses": None, "Due Payment": None},
        # Row 2: restaurant name
        {"Date": "Restaurant Name:", "Orders": restaurant_name,
         "Net Sales": None, "Total Tax": None, "Cash": None, "Card": None,
         "UPI": None, "My Amount": None, "Discount": None,
         "Service Charge": None, "CGST": None, "SGST": None,
         "Gst on sevice charge": None, "Round Off": None, "Total": None,
         "Expenses": None, "Due Payment": None},
        # Rows 3-4: blank
        {k: None for k in ["Date", "Orders", "Net Sales", "Total Tax", "Cash",
                            "Card", "UPI", "My Amount", "Discount",
                            "Service Charge", "CGST", "SGST",
                            "Gst on sevice charge", "Round Off", "Total",
                            "Expenses", "Due Payment"]},
        {k: None for k in ["Date", "Orders", "Net Sales", "Total Tax", "Cash",
                            "Card", "UPI", "My Amount", "Discount",
                            "Service Charge", "CGST", "SGST",
                            "Gst on sevice charge", "Round Off", "Total",
                            "Expenses", "Due Payment"]},
        # Row 5 is written as the DataFrame header (pandas writes it)
    ]
    if rupee_headers:
        header_and_data = {
            "Date": ["2026-04-01"],
            "Orders": [20],
            "Invoice Nos.": [5],
            "My Amount (₹)": [100000.0],
            "Discount (₹)": [0.0],
            "Net Sales (₹)(M.A - D)": [100000.0],
            "Total Tax (₹)": [10000.0],
            "Cash": [20000.0],
            "Card": [50000.0],
            "UPI": [30000.0],
            "Service Charge": [8000.0],
            "CGST": [1250.0],
            "SGST": [1250.0],
            "Gst on sevice charge": [400.0],
            "Round Off": [0.5],
            "Total (₹)": [118000.0],
            "Expenses": [500.0],
            "Pax": [32],
            "Due Payment": [0.0],
        }
    else:
        header_and_data = {
            "Date": ["2026-04-01"],
            "Orders": [20],
            "Net Sales": [100000.0],
            "Total Tax": [10000.0],
            "Cash": [20000.0],
            "Card": [50000.0],
            "UPI": [30000.0],
            "My Amount": [100000.0],
            "Discount": [0.0],
            "Service Charge": [8000.0],
            "CGST": [1250.0],
            "SGST": [1250.0],
            "Gst on sevice charge": [400.0],
            "Round Off": [0.5],
            "Total": [118000.0],
            "Expenses": [500.0],
            "Due Payment": [0.0],
        }
    if payment_cols:
        for col_name, value in payment_cols.items():
            header_and_data[col_name] = [value]
    if extra_cols:
        for col_name, value in extra_cols.items():
            header_and_data[col_name] = [value]

    buf2 = io.BytesIO()
    with pd.ExcelWriter(buf2, engine="openpyxl") as writer:
        # Write title rows manually then data
        title_df = pd.DataFrame(rows)
        title_df.to_excel(writer, index=False, header=False, startrow=0)
        data_df = pd.DataFrame(header_and_data)
        data_df.to_excel(writer, index=False, header=True, startrow=5)
    return buf2.getvalue()


def _item_report_bytes(restaurant_name: str = "Boteco") -> bytes:
    """Build a minimal Item Report Excel that the parser can read."""
    title_rows = [
        {"col0": "Date:", "col1": "2026-04-01 to 2026-04-01",
         **{f"x{i}": None for i in range(18)}},
        {"col0": "Name:", "col1": "Item Report With Customer/Order Details",
         **{f"x{i}": None for i in range(18)}},
        {"col0": "Restaurant Name:", "col1": restaurant_name,
         **{f"x{i}": None for i in range(18)}},
        {**{f"col{i}" if i < 2 else f"x{i-2}": None for i in range(20)}},
        {**{f"col{i}" if i < 2 else f"x{i-2}": None for i in range(20)}},
    ]
    data = {
        "Date": ["2026-04-01", "2026-04-01"],
        "Timestamp": ["2026-04-01 20:00:00", "2026-04-01 21:00:00"],
        "Invoice No.": ["1001", "1001"],
        "Payment Type": ["Cash", "Cash"],
        "Order Type": ["Dine In", "Dine In"],
        "Area": ["Ground Floor", "Ground Floor"],
        "Item Name": ["Item A", "Item B"],
        "Price": [200.0, 300.0],
        "Qty.": [2, 1],
        "Sub Total": [400.0, 300.0],
        "Discount": [0.0, 0.0],
        "Tax": [60.0, 45.0],
        "Final Total": [460.0, 345.0],
        "Status": ["Success", "Success"],
        "Table No.": ["T1", "T1"],
        "Server Name": ["Staff", "Staff"],
        "Covers": [2, 0],
        "Variation": ["", ""],
        "Category": ["Mains", "Salads"],
        "Group Name": ["Food - PFA", "Food - PFA"],
        "HSN": [None, None],
        "Phone": [None, None],
        "Name": [None, None],
        "Address": [None, None],
        "GST": [None, None],
        "Assign To": [None, None],
        "Non Taxable": [0.0, 0.0],
        "CGST Rate": [2.5, 2.5],
        "CGST Amount": [10.0, 7.5],
        "SGST Rate": [2.5, 2.5],
        "SGST Amount": [10.0, 7.5],
        "Service Charge Rate": [10.0, 10.0],
        "Service Charge Amount": [40.0, 30.0],
    }
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        title_df = pd.DataFrame(title_rows)
        title_df.to_excel(writer, index=False, header=False, startrow=0)
        data_df = pd.DataFrame(data)
        data_df.to_excel(writer, index=False, header=True, startrow=5)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# 1. file_detector tests
# ---------------------------------------------------------------------------


class TestFileDetector:
    def test_detects_growth_report_day_wise(self):
        import file_detector

        content = _growth_report_bytes()
        kind = file_detector.detect_file_type(content, "Growth_Report_Day_Wise_test.xlsx")
        assert kind == "growth_report_day_wise"

    def test_detects_item_order_details(self):
        import file_detector

        content = _item_report_bytes()
        kind = file_detector.detect_file_type(content, "Item_Report_With_CustomerOrder_test.xlsx")
        assert kind == "item_order_details"

    def test_growth_report_is_importable(self):
        import file_detector

        assert file_detector.is_importable("growth_report_day_wise")

    def test_item_report_is_importable(self):
        import file_detector

        assert file_detector.is_importable("item_order_details")

    def test_growth_report_has_higher_priority_than_item(self):
        import file_detector

        assert (
            file_detector.IMPORT_PRIORITY["growth_report_day_wise"]
            < file_detector.IMPORT_PRIORITY["item_order_details"]
        )

    def test_growth_report_filename_fallback(self):
        import file_detector

        # Minimal bytes that won't trigger content detection
        kind = file_detector.detect_file_type(b"", "growth_report_day_wise_test.xlsx")
        # With empty content, text is empty → falls through to filename hint
        kind2 = file_detector.detect_file_type(b"", "growth_report_2026.xlsx")
        assert kind == "growth_report_day_wise"
        assert kind2 == "growth_report_day_wise"


# ---------------------------------------------------------------------------
# 2. Location detection tests
# ---------------------------------------------------------------------------


class TestLocationDetection:
    """Tests for the exact-match-first outlet detection rule."""

    def _detect(self, restaurant_name: str, kind: str = "growth") -> dict | None:
        """Run detect_location_from_file against a synthetic file."""
        if kind == "growth":
            content = _growth_report_bytes(restaurant_name=restaurant_name)
            filename = f"Growth_Report_{restaurant_name}.xlsx"
        else:
            content = _item_report_bytes(restaurant_name=restaurant_name)
            filename = f"Item_Report_{restaurant_name}.xlsx"
        from services.location_detection import detect_location_from_file

        return detect_location_from_file(content, filename)

    def test_boteco_maps_to_indiqube(self):
        result = self._detect("Boteco")
        assert result is not None
        assert result["location_id"] == 1

    def test_boteco_bagmane_maps_to_bagmane(self):
        result = self._detect("Boteco - Bagmane")
        assert result is not None
        assert result["location_id"] == 2

    def test_bagmane_not_misclassified_as_boteco(self):
        """Critical: 'Boteco - Bagmane' must NOT match 'Boteco' alias."""
        result = self._detect("Boteco - Bagmane")
        assert result is not None
        # Must NOT be Indiqube (loc 1)
        assert result["location_id"] == 2, (
            f"Boteco - Bagmane was classified as location {result['location_id']} "
            "but should be 2 (Bagmane)"
        )

    def test_boteco_indiqube_explicit(self):
        result = self._detect("Boteco - Indiqube")
        assert result is not None
        assert result["location_id"] == 1

    def test_bagmane_short(self):
        result = self._detect("Bagmane")
        assert result is not None
        assert result["location_id"] == 2

    def test_item_report_boteco(self):
        result = self._detect("Boteco", kind="item")
        assert result is not None
        assert result["location_id"] == 1

    def test_item_report_bagmane(self):
        result = self._detect("Boteco - Bagmane", kind="item")
        assert result is not None
        assert result["location_id"] == 2


# ---------------------------------------------------------------------------
# 3. Payment mapping service tests
# ---------------------------------------------------------------------------


class TestPaymentMapping:
    def test_normalize_gpay_variants(self):
        from services.payment_mapping import normalize_payment_column

        for variant in ["Other [G PAY]", "Other [G  PAY]", "Other [GPAY]", "other [g pay]()"]:
            result = normalize_payment_column(variant)
            assert result == "gpay_sales", f"Expected gpay_sales for {variant!r}, got {result!r}"

    def test_normalize_bank_transfer(self):
        from services.payment_mapping import normalize_payment_column

        assert normalize_payment_column("Other [BANK TRANSFER]") == "bank_transfer_sales"

    def test_normalize_boh(self):
        from services.payment_mapping import normalize_payment_column

        assert normalize_payment_column("Other [BOH]") == "boh_sales"

    def test_normalize_not_paid_maps_to_due_payment(self):
        from services.payment_mapping import normalize_payment_column

        assert normalize_payment_column("Not Paid") == "due_payment_sales"
        assert normalize_payment_column("Due Payment") == "due_payment_sales"

    def test_normalize_cash_card_upi(self):
        from services.payment_mapping import normalize_payment_column

        assert normalize_payment_column("Cash") == "cash_sales"
        assert normalize_payment_column("Card") == "card_sales"
        assert normalize_payment_column("UPI") == "upi_sales"

    def test_generic_other_nonzero_raises(self):
        from services.payment_mapping import validate_payment_columns_or_raise

        df = pd.DataFrame({"Other [Unknown]": [100.0]})
        with pytest.raises(ValueError, match="Import blocked"):
            validate_payment_columns_or_raise(["Other [Unknown]"], df)

    def test_razorpay_zero_ok(self):
        from services.payment_mapping import validate_payment_columns_or_raise

        df = pd.DataFrame({"Other [Razorpay]": [0.0]})
        # Should NOT raise — zero is allowed for ignored columns
        validate_payment_columns_or_raise(["Other [Razorpay]"], df)

    def test_razorpay_nonzero_raises(self):
        from services.payment_mapping import validate_payment_columns_or_raise

        df = pd.DataFrame({"Other [Razorpay]": [50.0]})
        with pytest.raises(ValueError, match="Import blocked"):
            validate_payment_columns_or_raise(["Other [Razorpay]"], df)

    def test_unmapped_payment_nonzero_raises(self):
        from services.payment_mapping import validate_payment_columns_or_raise

        df = pd.DataFrame({"Other [XYZ]": [200.0]})
        with pytest.raises(ValueError, match="Import blocked"):
            validate_payment_columns_or_raise(["Other [XYZ]"], df)


# ---------------------------------------------------------------------------
# 4. Growth Report parser tests
# ---------------------------------------------------------------------------


class TestGrowthReportParser:
    def _parse(self, restaurant: str = "Boteco", **kwargs):
        from uploads.parsers.growth_report_day_wise import parse_growth_report_day_wise

        content = _growth_report_bytes(restaurant_name=restaurant, **kwargs)
        rows, errors, meta = parse_growth_report_day_wise(content, "test.xlsx", location_id=1)
        return rows, errors, meta

    def test_returns_daily_rows(self):
        rows, errors, meta = self._parse()
        assert not errors, f"Unexpected errors: {errors}"
        assert len(rows) == 1

    def test_row_has_required_fields(self):
        rows, errors, _ = self._parse()
        assert not errors
        row = rows[0]
        required = [
            "date",
            "order_count",
            "net_total",
            "gross_total",
            "cash_sales",
            "card_sales",
            "upi_sales",
            "gpay_sales",
            "bank_transfer_sales",
            "boh_sales",
            "due_payment_sales",
            "wallet_sales",
            "cgst",
            "sgst",
            "service_charge",
            "total_tax",
            "source_report",
        ]
        for field in required:
            assert field in row, f"Missing field: {field}"

    def test_source_report_value(self):
        rows, _, _ = self._parse()
        assert rows[0]["source_report"] == "growth_report_day_wise"

    def test_file_type_value(self):
        rows, _, _ = self._parse()
        assert rows[0]["file_type"] == "growth_report_day_wise"

    def test_location_id_embedded(self):
        rows, errors, _ = self._parse()
        assert not errors
        assert rows[0]["location_id"] == 1

    def test_gpay_maps_correctly(self):
        from uploads.parsers.growth_report_day_wise import parse_growth_report_day_wise

        content = _growth_report_bytes(payment_cols={"Other [G  PAY]": 15000.0})
        rows, errors, _ = parse_growth_report_day_wise(content, "test.xlsx", location_id=1)
        assert not errors, errors
        assert rows[0]["gpay_sales"] == 15000.0

    def test_not_paid_maps_to_due_payment(self):
        from uploads.parsers.growth_report_day_wise import parse_growth_report_day_wise

        content = _growth_report_bytes(payment_cols={"Not Paid": 500.0})
        rows, errors, _ = parse_growth_report_day_wise(content, "test.xlsx", location_id=1)
        assert not errors, errors
        assert rows[0]["due_payment_sales"] == 500.0

    def test_unmapped_nonzero_payment_blocks_import(self):
        from uploads.parsers.growth_report_day_wise import parse_growth_report_day_wise

        content = _growth_report_bytes(extra_cols={"Other [XYZ]": 100.0})
        rows, errors, meta = parse_growth_report_day_wise(content, "test.xlsx")
        assert rows == []
        assert any("Import blocked" in e for e in errors)
        assert meta.get("unmapped_payment_types")

    def test_meta_has_period(self):
        _, _, meta = self._parse()
        # period_start/end extracted from header rows
        assert "period_start" in meta
        assert "row_count" in meta
        assert meta["row_count"] == 1

    def test_rupee_headers_preserve_net_total_and_gross(self):
        """Regression: ₹-symbol headers (real Petpooja format) must not zero out values.

        FIELD_MAP has paired entries (e.g. "net sales (₹)(m.a - d)" and "net sales")
        for the same target.  The short form won't match real files, so the parser
        must not overwrite a correct long-form extraction with 0.
        """
        rows, errors, _ = self._parse(rupee_headers=True)
        assert not errors, f"Unexpected errors: {errors}"
        row = rows[0]
        assert row["net_total"] == 100000.0, f"net_total={row['net_total']}"
        assert row["gross_total"] == 118000.0, f"gross_total={row['gross_total']}"
        assert row["my_amount"] == 100000.0, f"my_amount={row['my_amount']}"
        assert row["total_tax"] == 10000.0, f"total_tax={row['total_tax']}"
        assert row["covers"] == 32, f"covers={row['covers']}"
        assert row["round_off"] == 0.5, f"round_off={row['round_off']}"
        assert row["expenses"] == 500.0, f"expenses={row['expenses']}"


# ---------------------------------------------------------------------------
# 5. Item Report category parser tests
# ---------------------------------------------------------------------------


class TestItemReportCategoryParser:
    def _parse(self, restaurant: str = "Boteco"):
        from uploads.parsers.item_report_category_summary import (
            parse_item_report_category_summary,
        )

        content = _item_report_bytes(restaurant_name=restaurant)
        rows, errors, meta = parse_item_report_category_summary(
            content, "test.xlsx", location_id=1
        )
        return rows, errors, meta

    def test_returns_category_rows(self):
        rows, errors, meta = self._parse()
        assert not errors, f"Unexpected errors: {errors}"
        assert len(rows) >= 1

    def test_row_has_required_fields(self):
        rows, errors, _ = self._parse()
        assert not errors
        row = rows[0]
        required = [
            "date",
            "category_name",
            "group_name",
            "normalized_category",
            "qty",
            "sub_total",
            "discount",
            "tax",
            "final_total",
            "cgst_amount",
            "sgst_amount",
            "service_charge_amount",
            "complimentary_amount",
            "cancelled_amount",
            "source_report",
        ]
        for field in required:
            assert field in row, f"Missing field: {field}"

    def test_source_report_value(self):
        rows, _, _ = self._parse()
        assert rows[0]["source_report"] == "item_report_customer_order_details"

    def test_food_pfa_normalized(self):
        rows, _, _ = self._parse()
        food_rows = [r for r in rows if "Food - PFA" in r.get("group_name", "")]
        assert food_rows, "No Food - PFA rows found"
        assert food_rows[0]["normalized_category"] == "Food"

    def test_sub_total_positive(self):
        rows, _, _ = self._parse()
        assert all(r["sub_total"] > 0 for r in rows)

    def test_location_id_embedded(self):
        rows, errors, _ = self._parse()
        assert not errors
        assert rows[0]["location_id"] == 1


# ---------------------------------------------------------------------------
# 6. database_writes helper test
# ---------------------------------------------------------------------------


class TestDatabaseWritesNewFlow:
    def test_build_daily_summary_includes_all_new_fields(self):
        from database_writes import build_daily_summary_row_new_flow

        data = {
            "gross_total": 100000,
            "net_total": 85000,
            "covers": 30,
            "my_amount": 85000,
            "total_tax": 10000,
            "round_off": 0.5,
            "expenses": 200,
            "due_payment_sales": 1000,
            "wallet_sales": 500,
            "upi_sales": 30000,
            "gpay_sales": 15000,
            "bank_transfer_sales": 0,
            "boh_sales": 0,
            "delivery_sales": 0,
            "pickup_sales": 0,
            "dine_in_sales": 85000,
            "menu_qr_sales": 0,
            "source_report": "growth_report_day_wise",
        }
        row = build_daily_summary_row_new_flow(1, "2026-04-01", data)

        new_fields = [
            "my_amount",
            "total_tax",
            "round_off",
            "expenses",
            "due_payment_sales",
            "wallet_sales",
            "upi_sales",
            "bank_transfer_sales",
            "boh_sales",
            "delivery_sales",
            "pickup_sales",
            "dine_in_sales",
            "menu_qr_sales",
            "source_report",
        ]
        for field in new_fields:
            assert field in row, f"New field missing from daily_summary row: {field}"

        assert row["location_id"] == 1
        assert row["date"] == "2026-04-01"
        assert row["source_report"] == "growth_report_day_wise"
        # gpay_sales must not be mapped to upi_sales
        assert row["gpay_sales"] == 15000.0
        assert row["upi_sales"] == 30000.0
