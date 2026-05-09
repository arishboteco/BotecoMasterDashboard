"""Tests for pure forecasting helper logic."""

import math

import pandas as pd

from tabs.forecasting import (
    calculate_forecast_days,
    generate_forecast_dates,
    linear_forecast,
    moving_average,
)


class TestLinearForecast:
    def test_returns_forecast_with_3_points(self):
        """Forecast should work with minimum 3 data points."""
        dates = pd.to_datetime(["2026-04-01", "2026-04-02", "2026-04-03"])
        values = [100, 200, 150]
        result = linear_forecast(dates, values, forecast_days=2)
        assert result is not None
        assert len(result) == 2

    def test_returns_none_when_fewer_than_3_points(self):
        dates = pd.to_datetime(["2026-04-01", "2026-04-02"])
        values = [100, 200]
        result = linear_forecast(dates, values, forecast_days=2)
        assert result is None

    def test_returns_forecast_with_correct_length(self):
        dates = pd.to_datetime([f"2026-04-{d:02d}" for d in range(1, 16)])
        values = [float(100 + i * 5) for i in range(15)]
        result = linear_forecast(dates, values, forecast_days=5)
        assert result is not None
        assert len(result) == 5

    def test_forecast_has_expected_keys(self):
        dates = pd.to_datetime([f"2026-04-{d:02d}" for d in range(1, 16)])
        values = [float(100 + i * 5) for i in range(15)]
        result = linear_forecast(dates, values, forecast_days=3)
        assert result is not None
        for entry in result:
            assert "date" in entry
            assert "value" in entry
            assert "upper" in entry
            assert "lower" in entry

    def test_flat_values_produce_stable_forecast(self):
        """Constant input should produce a forecast near that constant."""
        dates = pd.to_datetime([f"2026-04-{d:02d}" for d in range(1, 16)])
        values = [100.0] * 15
        result = linear_forecast(dates, values, forecast_days=3)
        assert result is not None
        for entry in result:
            # Should be close to 100, allowing for weekday multiplier rounding
            assert abs(entry["value"] - 100.0) < 15.0

    def test_std_dev_band_widens_with_distance(self):
        dates = pd.to_datetime([f"2026-04-{d:02d}" for d in range(1, 16)])
        values = [100.0 + float(i) * 5 for i in range(15)]
        result = linear_forecast(dates, values, forecast_days=7)
        assert result is not None
        first_band = result[0]["upper"] - result[0]["lower"]
        last_band = result[-1]["upper"] - result[-1]["lower"]
        assert last_band > first_band

    def test_forecast_values_are_realistic(self):
        """Forecast should stay in the ballpark of actual data, not explode."""
        dates = pd.to_datetime([f"2026-04-{d:02d}" for d in range(1, 8)])
        values = [80000, 95000, 110000, 130000, 150000, 120000, 200000]
        result = linear_forecast(dates, values, forecast_days=7)
        assert result is not None
        data_max = max(values)
        for entry in result:
            # Forecast should not exceed 3x the max or go below 0
            assert entry["value"] < data_max * 3
            assert entry["value"] >= 0

    def test_forecast_near_average_for_short_data(self):
        """With 5 points and no weekday data, forecast should be near recent average."""
        dates = pd.to_datetime(
            [
                "2026-04-01",
                "2026-04-02",
                "2026-04-03",
                "2026-04-04",
                "2026-04-05",
            ]
        )
        values = [100000, 120000, 110000, 130000, 115000]
        result = linear_forecast(dates, values, forecast_days=3)
        assert result is not None
        avg = sum(values) / len(values)
        for entry in result:
            # Should be within 30% of the average (no weekday pattern applied)
            assert abs(entry["value"] - avg) / avg < 0.30

    def test_lower_bound_never_negative(self):
        """Lower confidence bound should never go below zero."""
        dates = pd.to_datetime([f"2026-04-{d:02d}" for d in range(1, 8)])
        values = [10.0, 5.0, 8.0, 3.0, 7.0, 2.0, 6.0]
        result = linear_forecast(dates, values, forecast_days=7)
        assert result is not None
        for entry in result:
            assert entry["lower"] >= 0


class TestMovingAverage:
    def test_returns_same_length_as_input(self):
        values = [10, 20, 30, 40, 50, 60, 70, 80]
        result = moving_average(values, window=3)
        assert len(result) == len(values)

    def test_first_values_are_nan_when_window_exceeds_available(self):
        values = [10, 20, 30]
        result = moving_average(values, window=5)
        assert math.isnan(result[0])
        assert math.isnan(result[1])

    def test_computes_correct_3_window_average(self):
        values = [10.0, 20.0, 30.0, 40.0]
        result = moving_average(values, window=3)
        assert math.isnan(result[0])
        assert math.isnan(result[1])
        assert result[2] == 20.0
        assert result[3] == 30.0

    def test_window_of_1_returns_original(self):
        values = [10.0, 20.0, 30.0]
        result = moving_average(values, window=1)
        assert result == values


class TestGenerateForecastDates:
    def test_generates_correct_number_of_dates(self):
        last_date = pd.Timestamp("2026-04-15")
        result = generate_forecast_dates(last_date, forecast_days=5)
        assert len(result) == 5

    def test_dates_are_consecutive(self):
        last_date = pd.Timestamp("2026-04-15")
        result = generate_forecast_dates(last_date, forecast_days=3)
        assert result[0] == pd.Timestamp("2026-04-16")
        assert result[1] == pd.Timestamp("2026-04-17")
        assert result[2] == pd.Timestamp("2026-04-18")


class TestCalculateForecastDays:
    def test_this_week_returns_7_days(self):
        result = calculate_forecast_days("This Week", data_points=10)
        assert result == 7

    def test_last_week_returns_7_days(self):
        result = calculate_forecast_days("Last Week", data_points=10)
        assert result == 7

    def test_7d_returns_half_window_capped_at_7(self):
        result = calculate_forecast_days("7D", data_points=10, selected_range_days=7)
        assert result == 3

    def test_this_month_returns_days_until_month_end(self):
        result = calculate_forecast_days("This Month", data_points=10)
        assert result >= 1
        assert result <= 31

    def test_last_month_returns_30_days(self):
        result = calculate_forecast_days("Last Month", data_points=10)
        assert result == 30

    def test_30d_returns_7_days(self):
        result = calculate_forecast_days("30D", data_points=10, selected_range_days=30)
        assert result == 7

    def test_custom_returns_half_range_when_provided(self):
        result = calculate_forecast_days("Custom", data_points=10, selected_range_days=10)
        assert result == 5

    def test_qtd_returns_days_until_quarter_end(self):
        result = calculate_forecast_days("QTD", data_points=10)
        assert result >= 1
        assert result <= 92

    def test_insufficient_data_returns_0_days(self):
        """Less than 3 data points: no forecast possible."""
        result = calculate_forecast_days("This Month", data_points=2)
        assert result == 0

    def test_unknown_period_defaults_to_7_days(self):
        result = calculate_forecast_days("Unknown Period", data_points=10)
        assert result == 7
