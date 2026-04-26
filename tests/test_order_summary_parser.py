"""Tests for extracted Order Summary CSV parser."""

from uploads.parsers.order_summary import parse_order_summary_csv
import smart_upload


class TestOrderSummaryParser:
    def test_valid_success_order(self):
        content = ("date,my_amount,status,payment_type\n2026-04-01,100,SuccessOrder,GPay\n").encode(
            "utf-8"
        )

        parsed, notes = parse_order_summary_csv(content, "orders.csv")

        assert notes == []
        assert parsed is not None
        assert len(parsed) == 1
        assert parsed[0]["date"] == "2026-04-01"
        assert parsed[0]["net_total"] == 100.0

    def test_complimentary_is_excluded(self):
        content = (
            "date,my_amount,status,payment_type\n2026-04-01,100,Success Complimentary,Cash\n"
        ).encode("utf-8")

        parsed, notes = parse_order_summary_csv(content, "orders.csv")

        assert notes == []
        assert parsed is None

    def test_missing_required_columns(self):
        content = ("created_at,status,payment_type\n2026-04-01,SuccessOrder,Cash\n").encode("utf-8")

        parsed, notes = parse_order_summary_csv(content, "orders.csv")

        assert parsed is None
        assert notes == ["Order Summary CSV missing required columns (date / my_amount)."]

    def test_payment_bucket_mapping(self):
        content = (
            "date,my_amount,status,payment_type\n"
            "2026-04-01,100,SuccessOrder,Cash\n"
            "2026-04-01,50,SuccessOrder,Card\n"
            "2026-04-01,25,SuccessOrder,GPay\n"
            "2026-04-01,10,SuccessOrder,Zomato\n"
            "2026-04-01,5,SuccessOrder,Amazon Pay\n"
        ).encode("utf-8")

        parsed, _ = parse_order_summary_csv(content, "orders.csv")

        assert parsed is not None
        assert parsed[0]["cash_sales"] == 100.0
        assert parsed[0]["card_sales"] == 50.0
        assert parsed[0]["gpay_sales"] == 25.0
        assert parsed[0]["zomato_sales"] == 10.0
        assert parsed[0]["other_sales"] == 5.0


class TestSmartUploadCompatibility:
    def test_compatibility_wrapper_calls_extracted_parser(self, monkeypatch):
        called = {}

        def _fake_parse(content, filename):
            called["args"] = (content, filename)
            return [{"date": "2026-04-01", "net_total": 1.0, "gross_total": 1.0}], []

        monkeypatch.setattr(smart_upload, "parse_order_summary_csv", _fake_parse)

        parsed, notes = smart_upload._parse_order_summary_csv(b"csv", "orders.csv")

        assert called["args"] == (b"csv", "orders.csv")
        assert parsed is not None
        assert notes == []
