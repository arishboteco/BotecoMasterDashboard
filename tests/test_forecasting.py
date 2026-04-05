"""Tests for pure forecasting helper logic."""

import math

import pandas as pd

from tabs.forecasting import (
    generate_forecast_dates,
    linear_forecast,
    moving_average,
)


class TestLinearForecast:
    def test_returns_none_when_fewer_than_7_points(self):
        dates = pd.to_datetime(["2026-04-01", "2026-04-02", "2026-04-03"])
        values = [100, 200, 150]
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

    def test_upward_trend_produces_increasing_forecast(self):
        dates = pd.to_datetime([f"2026-04-{d:02d}" for d in range(1, 16)])
        values = [float(100 + i * 10) for i in range(15)]
        result = linear_forecast(dates, values, forecast_days=5)
        assert result is not None
        assert result[0]["value"] < result[-1]["value"]

    def test_flat_values_produce_flat_forecast(self):
        dates = pd.to_datetime([f"2026-04-{d:02d}" for d in range(1, 16)])
        values = [100.0] * 15
        result = linear_forecast(dates, values, forecast_days=3)
        assert result is not None
        for entry in result:
            assert abs(entry["value"] - 100.0) < 1.0

    def test_std_dev_band_widens_with_distance(self):
        dates = pd.to_datetime([f"2026-04-{d:02d}" for d in range(1, 16)])
        values = [100.0 + float(i) * 5 for i in range(15)]
        result = linear_forecast(dates, values, forecast_days=7)
        assert result is not None
        first_band = result[0]["upper"] - result[0]["lower"]
        last_band = result[-1]["upper"] - result[-1]["lower"]
        assert last_band > first_band


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
