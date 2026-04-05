"""Formatting tests for sheet report helpers."""

import sheet_reports


class TestRupeeFormatting:
    def test_decimal_currency_rounds_to_whole_rupees(self):
        assert sheet_reports._r(72885.08) == "₹72,885"

    def test_small_decimal_currency_rounds_to_whole_rupees(self):
        assert sheet_reports._r(1433.66) == "₹1,434"


class TestForecastFormatting:
    def test_currency_formatter_handles_forecast_values(self):
        assert sheet_reports._r(300000.4) == "₹300,000"
