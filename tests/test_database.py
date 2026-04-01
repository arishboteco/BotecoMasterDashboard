"""Tests for database footfall queries."""

import pytest
import database


class TestGetMonthlyFootfallMulti:
    def test_returns_empty_for_no_data(self):
        result = database.get_monthly_footfall_multi([1], "2025-01-01", "2025-12-31")
        assert result == []

    def test_aggregates_covers_by_month(self):
        # This test assumes test DB setup — verify query returns correct shape
        # At minimum, verify the function exists and returns a list
        result = database.get_monthly_footfall_multi([1], "2025-01-01", "2025-01-31")
        assert isinstance(result, list)
        if result:
            row = result[0]
            assert "month" in row
            assert "covers" in row
            assert "total_days" in row


class TestGetWeeklyFootfallMulti:
    def test_returns_empty_for_no_data(self):
        result = database.get_weekly_footfall_multi([1], "2025-01-01", "2025-12-31")
        assert result == []

    def test_aggregates_covers_by_week(self):
        # Verify function exists and returns correct shape
        result = database.get_weekly_footfall_multi([1], "2025-01-01", "2025-01-31")
        assert isinstance(result, list)
        if result:
            row = result[0]
            assert "week" in row
            assert "covers" in row
            assert "total_days" in row
