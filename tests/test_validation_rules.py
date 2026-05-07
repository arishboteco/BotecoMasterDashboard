"""Tests for Phase 2 data accuracy fixes.

Covers:
- validate_data() warning rules (net>gross, negative payments, payment mismatch)
- compute_daily_target() using actual month lengths
- _pct() formatting for sub-1% values
- Turns = None when seat_count not configured
- Duplicate date filter removal (regression)
"""

from __future__ import annotations

import os
import sys

# Ensure project root is on path when running from tests/ directory
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import scope
import utils
from pos_parser import calculate_derived_metrics, validate_data
from sheet_reports import _pct

# ── validate_data ─────────────────────────────────────────────────────────────


def _valid_base() -> dict:
    """Minimal valid record."""
    return {
        "date": "2026-04-15",
        "gross_total": 50000,
        "net_total": 45000,
    }


def test_valid_record_no_errors_no_warnings():
    ok, errors, warnings = validate_data(_valid_base())
    assert ok
    assert errors == []
    assert warnings == []


def test_missing_date_is_error():
    data = _valid_base()
    del data["date"]
    ok, errors, warnings = validate_data(data)
    assert not ok
    assert any("Date" in e for e in errors)


def test_zero_gross_is_error():
    data = _valid_base()
    data["gross_total"] = 0
    ok, errors, warnings = validate_data(data)
    assert not ok
    assert any("Gross" in e for e in errors)


def test_zero_net_is_error():
    data = _valid_base()
    data["net_total"] = 0
    ok, errors, warnings = validate_data(data)
    assert not ok
    assert any("Net" in e for e in errors)


def test_net_exceeds_gross_is_warning_not_error():
    data = _valid_base()
    data["net_total"] = 60000  # net > gross
    data["gross_total"] = 50000
    ok, errors, warnings = validate_data(data)
    # Should still save (ok=True for blocking errors), but has a warning
    assert errors == []
    assert any("exceeds gross" in w for w in warnings)


def test_negative_cash_sales_is_warning():
    data = _valid_base()
    data["cash_sales"] = -500
    ok, errors, warnings = validate_data(data)
    assert any("negative" in w for w in warnings)


def test_negative_gpay_sales_is_warning():
    data = _valid_base()
    data["gpay_sales"] = -100
    ok, errors, warnings = validate_data(data)
    assert any("negative" in w for w in warnings)


def test_payment_sum_mismatch_large_triggers_warning():
    data = _valid_base()
    # net = 45000 but payment sum = 10000 (78% off)
    data["cash_sales"] = 5000
    data["card_sales"] = 5000
    ok, errors, warnings = validate_data(data)
    assert any("differs from net" in w for w in warnings)


def test_payment_sum_within_2pct_no_warning():
    data = _valid_base()
    # net = 45000, payments = 45500 → 1.1% off (within tolerance)
    data["cash_sales"] = 20000
    data["card_sales"] = 25500
    ok, errors, warnings = validate_data(data)
    assert not any("differs from net" in w for w in warnings)


# ── compute_daily_target ──────────────────────────────────────────────────────


def test_daily_target_february_2026():
    """February 2026 has 28 days."""
    target = utils.compute_daily_target(5_000_000, 2026, 2)
    assert target == 5_000_000 / 28


def test_daily_target_february_2024_leap():
    """February 2024 is a leap year (29 days)."""
    target = utils.compute_daily_target(5_000_000, 2024, 2)
    assert target == 5_000_000 / 29


def test_daily_target_march():
    """March has 31 days."""
    target = utils.compute_daily_target(5_000_000, 2026, 3)
    assert target == 5_000_000 / 31


def test_daily_target_april():
    """April has 30 days."""
    target = utils.compute_daily_target(5_000_000, 2026, 4)
    assert target == 5_000_000 / 30


def test_daily_target_not_divided_by_30_for_february():
    """February target must NOT equal monthly/30."""
    target = utils.compute_daily_target(5_000_000, 2026, 2)
    assert target != 5_000_000 / 30


# ── _pct() formatting ─────────────────────────────────────────────────────────


def test_pct_zero():
    assert _pct(0) == "0%"


def test_pct_whole_number():
    assert _pct(5) == "5%"
    assert _pct(100) == "100%"
    assert _pct(99) == "99%"


def test_pct_sub_one_shows_decimal():
    assert _pct(0.3) == "0.3%"
    assert _pct(0.7) == "0.7%"
    assert _pct(0.1) == "0.1%"


def test_pct_sub_one_not_rounded_to_zero():
    """Critical: 0.3% must not display as 0%."""
    result = _pct(0.3)
    assert result != "0%"


def test_pct_negative_sub_one():
    assert _pct(-0.5) == "-0.5%"


# ── Turns calculation ─────────────────────────────────────────────────────────


def test_turns_none_when_no_seat_count():
    """Turns should be None when seat_count is not configured."""
    result = calculate_derived_metrics(
        {
            "covers": 150,
            "net_total": 80000,
            # no seat_count
        }
    )
    assert result["turns"] is None


def test_turns_calculated_with_seat_count():
    """Turns should calculate correctly when seat_count is provided."""
    result = calculate_derived_metrics(
        {
            "covers": 150,
            "net_total": 80000,
            "seat_count": 40,
        }
    )
    assert result["turns"] == round(150 / 40, 1)


def test_turns_not_covers_over_100():
    """Turns must not default to covers/100 (the old broken fallback)."""
    result = calculate_derived_metrics(
        {
            "covers": 150,
            "net_total": 80000,
        }
    )
    # Old code would give 1.5; now should be None
    assert result["turns"] != 1.5
    assert result["turns"] is None


def test_aggregate_daily_summaries_does_not_fallback_to_covers_over_100():
    """Combined aggregation should not invent turns from covers / 100."""
    result = scope.aggregate_daily_summaries(
        [
            {
                "date": "2026-04-27",
                "covers": 48,
                "net_total": 44010,
                "target": 400000,
            },
            {
                "date": "2026-04-27",
                "covers": 0,
                "net_total": 0,
                "target": 400000,
            },
        ]
    )

    assert result is not None
    assert result["turns"] is None


# ── Duplicate date filter regression ─────────────────────────────────────────


def test_calculate_mtd_metrics_multi_does_not_double_filter():
    """MTD calculation should run without crash (regression for duplicate filter removal)."""
    from unittest.mock import patch

    mock_summaries = [
        {
            "date": "2026-04-01",
            "net_total": 45000,
            "covers": 120,
            "discount": 0,
            "complimentary": 0,
        },
        {
            "date": "2026-04-10",
            "net_total": 52000,
            "covers": 140,
            "discount": 500,
            "complimentary": 0,
        },
        {
            "date": "2026-04-15",
            "net_total": 48000,
            "covers": 130,
            "discount": 200,
            "complimentary": 0,
        },
        # This date is after as_of_date and should be excluded
        {
            "date": "2026-04-20",
            "net_total": 60000,
            "covers": 160,
            "discount": 0,
            "complimentary": 0,
        },
    ]

    from pos_parser import calculate_mtd_metrics_multi

    with patch("database.get_summaries_for_month_multi", return_value=mock_summaries):
        result = calculate_mtd_metrics_multi.__wrapped__(
            location_ids=[1],
            target_monthly=5_000_000,
            year=2026,
            month=4,
            as_of_date="2026-04-15",
        )

    assert "mtd_pct_target" in result
    # Only 3 days should count (Apr 20 excluded)
    assert result["days_counted"] == 3
    assert result["mtd_net_sales"] == 45000 + 52000 + 48000
