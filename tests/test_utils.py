"""Tests for shared formatting helpers."""

import utils


class TestFormatPercent:
    def test_rounds_without_decimals(self):
        assert utils.format_percent(74.2) == "74%"

    def test_handles_none_as_zero(self):
        assert utils.format_percent(None) == "0%"
