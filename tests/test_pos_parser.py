"""Tests for pos_parser helper functions."""

import pytest
from pos_parser import (
    _f,
    _i,
    _norm_header,
    _parse_date,
    _cell_date_to_iso,
    _payment_bucket,
    _normalize_group_category,
)


class TestF:
    def test_numeric_string(self):
        assert _f("1234.56") == 1234.56

    def test_string_with_commas(self):
        assert _f("1,234,567") == 1234567.0

    def test_none(self):
        assert _f(None) == 0.0

    def test_nan(self):
        import pandas as pd

        assert _f(float("nan")) == 0.0

    def test_empty_string(self):
        assert _f("") == 0.0

    def test_rupee_symbol(self):
        assert _f("₹1,500") == 1500.0


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
