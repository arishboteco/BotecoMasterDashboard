"""Tests for core date-range helper functions."""

import datetime as dt

import pytest

from core.dates import date_range_inclusive, month_bounds, normalize_date_str


def test_month_bounds_february_leap_year():
    start, end = month_bounds(2024, 2)

    assert start == "2024-02-01"
    assert end == "2024-03-01"


def test_month_bounds_december_rollover():
    start, end = month_bounds(2025, 12)

    assert start == "2025-12-01"
    assert end == "2026-01-01"


def test_month_bounds_normal_month():
    start, end = month_bounds(2026, 4)

    assert start == "2026-04-01"
    assert end == "2026-05-01"


def test_date_range_inclusive_includes_endpoints():
    values = list(date_range_inclusive("2026-04-01", "2026-04-03"))

    assert values == ["2026-04-01", "2026-04-02", "2026-04-03"]


def test_normalize_date_str_supports_string_and_datetime_types():
    assert normalize_date_str("2026-04-26") == "2026-04-26"
    assert normalize_date_str(dt.date(2026, 4, 26)) == "2026-04-26"
    assert normalize_date_str(dt.datetime(2026, 4, 26, 12, 30, 0)) == "2026-04-26"


def test_normalize_date_str_rejects_unsupported_inputs():
    with pytest.raises(ValueError):
        normalize_date_str("26/04/2026")

    with pytest.raises(ValueError):
        normalize_date_str(None)


def test_date_range_inclusive_rejects_reverse_range():
    with pytest.raises(ValueError):
        list(date_range_inclusive("2026-04-10", "2026-04-09"))
