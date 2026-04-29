"""Tests for pos_parser helper functions."""

from pos_parser import (
    _f,
    _i,
    _norm_header,
    _parse_date,
    _cell_date_to_iso,
    _payment_bucket,
    _normalize_group_category,
    calculate_mtd_metrics,
    calculate_mtd_metrics_multi,
)


class TestF:
    def test_numeric_string(self):
        assert _f("1234.56") == 1234.56

    def test_string_with_commas(self):
        assert _f("1,234,567") == 1234567.0

    def test_none(self):
        assert _f(None) == 0.0

    def test_nan(self):
        assert _f(float("nan")) == 0.0

    def test_empty_string(self):
        assert _f("") == 0.0

    def test_rupee_symbol(self):
        assert _f("₹1,500") == 1500.0


class TestI:
    def test_float_to_int(self):
        assert _i(3.7) == 4

    def test_string_number(self):
        assert _i("42") == 42

    def test_none(self):
        assert _i(None) == 0

    def test_string_with_commas(self):
        assert _i("1,234") == 1234


class TestNormHeader:
    def test_normalizes_whitespace(self):
        assert _norm_header("  Sub   Total  ") == "sub total"

    def test_lowercase(self):
        assert _norm_header("Final TOTAL") == "final total"

    def test_none(self):
        assert _norm_header(None) == ""


class TestParseDate:
    def test_iso_format(self):
        assert _parse_date("2024-03-15") == "2024-03-15"

    def test_dd_mm_yyyy(self):
        assert _parse_date("15-03-2024") == "2024-03-15"

    def test_dd_mmm_yyyy(self):
        assert _parse_date("15-Mar-2024") == "2024-03-15"

    def test_invalid(self):
        assert _parse_date("not-a-date") is None


class TestCellDateToIso:
    def test_datetime_object(self):
        from datetime import datetime

        dt = datetime(2024, 3, 15)
        assert _cell_date_to_iso(dt) == "2024-03-15"

    def test_none(self):
        assert _cell_date_to_iso(None) is None

    def test_total_string(self):
        assert _cell_date_to_iso("total") is None


class TestPaymentBucket:
    def test_cash(self):
        assert _payment_bucket("Cash") == "cash"

    def test_gpay(self):
        assert _payment_bucket("G Pay") == "gpay"
        assert _payment_bucket("gpay") == "gpay"
        assert _payment_bucket("Google Pay") == "gpay"

    def test_zomato(self):
        assert _payment_bucket("Zomato") == "zomato"

    def test_card(self):
        assert _payment_bucket("Credit Card") == "card"
        assert _payment_bucket("Debit") == "card"

    def test_other(self):
        assert _payment_bucket("Wallet") == "other"
        assert _payment_bucket("") == "other"


class TestNormalizeGroupCategory:
    def test_coffee(self):
        assert _normalize_group_category("Coffee") == "Coffee"

    def test_beer(self):
        assert _normalize_group_category("Beer & Ciders") == "Beer"

    def test_liquor(self):
        assert _normalize_group_category("Liquor") == "Liquor"
        assert _normalize_group_category("Spirits") == "Liquor"

    def test_soft_beverages(self):
        assert _normalize_group_category("Soft Drinks") == "Soft Beverages"

    def test_food(self):
        assert _normalize_group_category("Food") == "Food"

    def test_unknown(self):
        assert _normalize_group_category("Misc") == "Misc"


class TestMtdComplimentary:
    def test_single_location_includes_mtd_complimentary(self, monkeypatch):
        monkeypatch.setattr(
            "database.get_summaries_for_month",
            lambda location_id, year, month: [
                {
                    "date": "2026-04-01",
                    "net_total": 1000,
                    "covers": 10,
                    "discount": 50,
                    "complimentary": 120,
                },
                {
                    "date": "2026-04-02",
                    "net_total": 500,
                    "covers": 5,
                    "discount": 0,
                    "complimentary": 30,
                },
            ],
        )

        out = calculate_mtd_metrics(1, target_monthly=10000, year=2026, month=4)

        assert out["mtd_complimentary"] == 150

    def test_multi_location_includes_mtd_complimentary(self, monkeypatch):
        monkeypatch.setattr(
            "database.get_summaries_for_month_multi",
            lambda location_ids, year, month: [
                {
                    "date": "2026-04-01",
                    "net_total": 1000,
                    "covers": 10,
                    "discount": 50,
                    "complimentary": 100,
                },
                {
                    "date": "2026-04-01",
                    "net_total": 700,
                    "covers": 7,
                    "discount": 25,
                    "complimentary": 40,
                },
            ],
        )

        out = calculate_mtd_metrics_multi(
            [1, 2], target_monthly=20000, year=2026, month=4
        )

        assert out["mtd_complimentary"] == 140
