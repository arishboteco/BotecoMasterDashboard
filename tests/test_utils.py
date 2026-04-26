"""Tests for shared formatting helpers."""

import utils


class TestFormatPercent:
    def test_formats_with_2_decimals(self):
        assert utils.format_percent(74.2) == "74.20%"

    def test_handles_none_as_zero(self):
        assert utils.format_percent(None) == "0.00%"


class TestGetDaysInMonth:
    def test_returns_31_for_december(self):
        assert utils.get_days_in_month(2025, 12) == 31

    def test_returns_29_for_leap_february(self):
        assert utils.get_days_in_month(2024, 2) == 29
