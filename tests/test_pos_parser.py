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
    validate_growth_day,
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


class TestMtdTargetPercentage:
    def test_single_location_uses_full_month_target_for_mtd_pct(self, monkeypatch):
        monkeypatch.setattr(
            "database.get_summaries_for_month",
            lambda location_id, year, month: [
                {"date": "2026-04-01", "net_total": 400_000, "covers": 100},
                {"date": "2026-04-02", "net_total": 200_000, "covers": 50},
            ],
        )

        out = calculate_mtd_metrics(
            1,
            target_monthly=4_000_000,
            year=2026,
            month=4,
            as_of_date="2026-04-15",
        )

        assert out["mtd_net_sales"] == 600_000
        assert out["mtd_pct_target"] == 15.0


class TestMtdGrossSales:
    def test_uses_my_amount_when_present(self, monkeypatch):
        monkeypatch.setattr(
            "database.get_summaries_for_month",
            lambda location_id, year, month: [
                {
                    "date": "2026-04-01",
                    "net_total": 950,
                    "discount": 50,
                    "my_amount": 1000,
                    "covers": 10,
                },
                {
                    "date": "2026-04-02",
                    "net_total": 500,
                    "discount": 0,
                    "my_amount": 500,
                    "covers": 5,
                },
            ],
        )

        out = calculate_mtd_metrics(1, target_monthly=10_000, year=2026, month=4)

        # Gross (My Amount) is reported separately from net-of-discount sales;
        # target/APC metrics stay on the net figure.
        assert out["mtd_gross_sales"] == 1500
        assert out["mtd_net_sales"] == 1450
        assert out["mtd_discount"] == 50

    def test_falls_back_to_net_plus_discount_when_my_amount_missing(self, monkeypatch):
        monkeypatch.setattr(
            "database.get_summaries_for_month_multi",
            lambda location_ids, year, month: [
                {"date": "2026-04-01", "net_total": 900, "discount": 100, "covers": 10},
            ],
        )

        out = calculate_mtd_metrics_multi([1, 2], target_monthly=10_000, year=2026, month=4)

        assert out["mtd_gross_sales"] == 1000
        assert out["mtd_net_sales"] == 900


def _clean_growth_day(**overrides):
    """A Growth Report day that should produce zero validate_growth_day warnings."""
    row = {
        "net_total": 100000.0,
        "gross_total": 110000.0,
        "my_amount": 101000.0,
        "discount": 1000.0,
        "covers": 40,
        "order_count": 40,
        "cash_sales": 55000.0,
        "card_sales": 55000.0,
        "gpay_sales": 0.0,
        "zomato_sales": 0.0,
        "other_sales": 0.0,
        "upi_sales": 0.0,
        "wallet_sales": 0.0,
        "due_payment_sales": 0.0,
        "bank_transfer_sales": 0.0,
        "boh_sales": 0.0,
    }
    row.update(overrides)
    return row


class TestValidateGrowthDay:
    def test_clean_day_has_no_warnings(self):
        assert validate_growth_day(_clean_growth_day()) == []

    def test_flags_broken_net_identity(self):
        warnings = validate_growth_day(
            _clean_growth_day(my_amount=101000.0, discount=1000.0, net_total=90000.0)
        )
        assert len(warnings) == 1
        assert "My Amount" in warnings[0]

    def test_zero_my_amount_skips_identity_check(self):
        # Legacy-flow rows never populate my_amount — must not false-positive.
        # net_total still needs to be consistent with the other fields
        # (within gross_total, payments summing to gross) to isolate this.
        warnings = validate_growth_day(
            _clean_growth_day(
                my_amount=0.0,
                discount=500.0,
                net_total=100000.0,
                cash_sales=55000.0,
                card_sales=55000.0,
            )
        )
        assert warnings == []

    def test_flags_net_exceeding_gross(self):
        warnings = validate_growth_day(
            _clean_growth_day(net_total=120000.0, gross_total=110000.0)
        )
        assert any("exceeds gross total" in w for w in warnings)

    def test_flags_negative_payment_field(self):
        warnings = validate_growth_day(_clean_growth_day(card_sales=-500.0))
        assert any("card_sales" in w for w in warnings)

    def test_flags_payments_exceeding_gross(self):
        # Standard payments alone should never exceed gross_total.
        warnings = validate_growth_day(
            _clean_growth_day(gross_total=110000.0, cash_sales=90000.0, card_sales=90000.0)
        )
        assert any("exceed gross total" in w for w in warnings)

    def test_does_not_flag_undercounted_payments(self):
        # One-sided: dynamic payment types (UPI aggregators, Zomato, etc.)
        # live outside these fields, so a shortfall alone is not a warning.
        warnings = validate_growth_day(
            _clean_growth_day(gross_total=110000.0, cash_sales=10000.0, card_sales=10000.0)
        )
        assert warnings == []

    def test_flags_missing_covers_on_trading_day(self):
        warnings = validate_growth_day(_clean_growth_day(covers=0, order_count=0))
        assert any("Covers" in w for w in warnings)

    def test_zero_net_day_skips_covers_check(self):
        # A genuinely closed day: no sales anywhere, so every field is zero.
        warnings = validate_growth_day(
            _clean_growth_day(
                net_total=0.0,
                gross_total=0.0,
                my_amount=0.0,
                discount=0.0,
                cash_sales=0.0,
                card_sales=0.0,
                covers=0,
                order_count=0,
            )
        )
        assert warnings == []
