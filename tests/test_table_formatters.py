"""Tests for table_formatters module."""

import pandas as pd
import pytest
from tabs import table_formatters


class TestFormatDailyDataTable:
    """Test daily data table formatter."""

    def test_returns_dataframe(self):
        """Test that formatter returns a DataFrame."""
        df = pd.DataFrame(
            {
                "date": ["2026-04-01", "2026-04-02"],
                "covers": [100, 110],
                "net_total": [50000, 55000],
                "target": [45000, 45000],
                "achievement": [111.1, 122.2],
            }
        )
        result = table_formatters.format_daily_data_table(df, pd.DataFrame(), False)
        assert isinstance(result, pd.DataFrame)

    def test_includes_totals_row(self):
        """Test that totals row is included."""
        df = pd.DataFrame(
            {
                "date": ["2026-04-01", "2026-04-02"],
                "covers": [100, 100],
                "net_total": [50000, 50000],
                "target": [45000, 45000],
                "achievement": [111.1, 111.1],
            }
        )
        result = table_formatters.format_daily_data_table(df, pd.DataFrame(), False)
        assert "TOTAL" in result["Date"].values

    def test_formats_currency(self):
        """Test that amounts are formatted as currency."""
        df = pd.DataFrame(
            {
                "date": ["2026-04-01"],
                "covers": [100],
                "net_total": [130235],
                "target": [100000],
                "achievement": [130.2],
            }
        )
        result = table_formatters.format_daily_data_table(df, pd.DataFrame(), False)
        # Should have Indian format
        assert any("₹" in str(val) for val in result["Net Sales"])


class TestBuildCategoryDetailTable:
    """Test category detail table builder."""

    def test_includes_all_categories(self):
        """Test that all categories are shown."""
        df = pd.DataFrame(
            {
                "category": ["Food", "Liquor", "Coffee"],
                "amount": [6500, 2800, 700],
            }
        )
        result = table_formatters.build_category_detail_table(df)
        assert len(result) == 4  # 3 categories + 1 totals row

    def test_includes_totals_row_with_100_percent(self):
        """Test that totals row shows 100%."""
        df = pd.DataFrame(
            {
                "category": ["Food", "Liquor"],
                "amount": [5000, 5000],
            }
        )
        result = table_formatters.build_category_detail_table(df)
        totals = result[result["Category"] == "TOTAL"]
        assert "100.0%" in totals["% of Total"].values


class TestBuildWeekdayDetail:
    """Test weekday detail table builder."""

    def test_returns_all_days(self):
        """Test that all 7 weekdays are returned."""
        dates = pd.date_range("2026-04-01", periods=14)  # 2 weeks
        df = pd.DataFrame(
            {
                "date": dates.strftime("%Y-%m-%d"),
                "net_total": [50000] * 14,
                "covers": [100] * 14,
            }
        )
        result = table_formatters.build_weekday_detail(df, dates[0].date())
        # Should have 7 days
        assert len(result) >= 7
