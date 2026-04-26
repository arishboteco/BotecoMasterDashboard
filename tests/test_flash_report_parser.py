"""Tests for extracted Flash Report parser."""

from __future__ import annotations

from io import BytesIO

import pandas as pd

import smart_upload
from uploads.parsers.flash_report import parse_flash_report


def _build_flash_report_xlsx(rows: list[list[object]]) -> bytes:
    """Build an in-memory flash report workbook from row values."""
    df = pd.DataFrame(rows)
    out = BytesIO()
    df.to_excel(out, index=False, header=False)
    return out.getvalue()


class TestFlashReportParser:
    def test_parse_flash_report_with_summary_payment_and_categories(self):
        content = _build_flash_report_xlsx(
            [
                ["Date", "2026-04-10"],
                ["", ""],
                [
                    "Orders",
                    "Net Sales",
                    "Total",
                    "Cash",
                    "CGST",
                    "SGST",
                    "Service Charge",
                    "Discount",
                    "Pax",
                ],
                [10, 1000, 1100, 200, 50, 50, 25, 10, 20],
                ["Payment Wise", ""],
                ["Cash", 200],
                ["Card", 300],
                ["G Pay", 400],
                ["Zomato", 50],
                ["Amazon Pay", 50],
                ["Total", 1000],
                ["Category Wise", ""],
                ["Category", "Net Sales"],
                ["Food", 700],
                ["Coffee", 300],
                ["Total", 1000],
            ]
        )

        parsed, notes = parse_flash_report(content, "flash.xlsx")

        assert notes == []
        assert parsed is not None
        assert len(parsed) == 1
        rec = parsed[0]
        assert rec["date"] == "2026-04-10"
        assert rec["net_total"] == 1000.0
        assert rec["gross_total"] == 1100.0
        assert rec["cash_sales"] == 200.0
        assert rec["card_sales"] == 300.0
        assert rec["gpay_sales"] == 400.0
        assert rec["zomato_sales"] == 50.0
        assert rec["other_sales"] == 50.0
        assert rec["service_charge"] == 25.0
        assert rec["covers"] == 20
        assert rec["categories"] == [
            {"category": "Food", "qty": 0, "amount": 700.0},
            {"category": "Coffee", "qty": 0, "amount": 300.0},
        ]

    def test_returns_error_when_date_missing(self):
        content = _build_flash_report_xlsx([["Orders", "Net Sales"], [1, 100]])

        parsed, notes = parse_flash_report(content, "flash.xlsx")

        assert parsed is None
        assert notes == ["Flash Report: could not extract date."]


class TestSmartUploadFlashCompatibility:
    def test_compatibility_wrapper_calls_extracted_parser(self, monkeypatch):
        called = {}

        def _fake_parse(content, filename):
            called["args"] = (content, filename)
            return [{"date": "2026-04-10", "net_total": 1.0, "gross_total": 1.0}], []

        monkeypatch.setattr(smart_upload, "parse_flash_report", _fake_parse)

        parsed, notes = smart_upload._parse_flash_report(b"xlsx", "flash.xlsx")

        assert called["args"] == (b"xlsx", "flash.xlsx")
        assert parsed is not None
        assert notes == []
