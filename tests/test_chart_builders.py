"""Tests for chart_builders module."""

import pandas as pd
from tabs import chart_builders


class TestBuildSalesTrendChart:
    """Test sales trend chart builder."""

    def test_returns_figure(self):
        """Test that chart builder returns a Figure."""
        df = pd.DataFrame(
            {
                "date": ["2026-04-01", "2026-04-02", "2026-04-03"],
                "net_total": [50000, 75000, 60000],
            }
        )
        fig = chart_builders.build_sales_trend_chart(
            df, pd.DataFrame(), False, "Last 7 Days"
        )
        assert fig is not None
        assert len(fig.data) >= 1  # At least one trace

    def test_includes_7day_ma_for_long_periods(self):
        """Test that 7-day MA is included for periods >=7 days."""
        dates = pd.date_range("2026-04-01", periods=10)
        df = pd.DataFrame(
            {
                "date": dates.strftime("%Y-%m-%d"),
                "net_total": [50000 + i * 1000 for i in range(10)],
            }
        )
        fig = chart_builders.build_sales_trend_chart(
            df, pd.DataFrame(), False, "Last 30 Days"
        )
        # Should have 2 traces: actual sales + 7-day MA
        assert len(fig.data) == 2


class TestBuildAPCChart:
    """Test APC chart builder."""

    def test_returns_figure_with_apc_data(self):
        """Test chart returns Figure when APC data exists."""
        df = pd.DataFrame(
            {
                "date": ["2026-04-01", "2026-04-02"],
                "apc": [2100, 2150],
            }
        )
        fig = chart_builders.build_apc_chart(df)
        assert fig is not None

    def test_returns_none_without_apc_data(self):
        """Test chart returns None when no APC data."""
        df = pd.DataFrame(
            {
                "date": ["2026-04-01"],
                "net_total": [50000],
            }
        )
        fig = chart_builders.build_apc_chart(df)
        assert fig is None

    def test_yaxis_starts_at_zero(self):
        """Test that y-axis range starts at 0."""
        df = pd.DataFrame(
            {
                "date": ["2026-04-01", "2026-04-02"],
                "apc": [2100, 2150],
            }
        )
        fig = chart_builders.build_apc_chart(df)
        assert fig.layout.yaxis.range[0] == 0


class TestBuildWeekdayChart:
    """Test weekday analysis chart builder."""

    def test_returns_figure(self):
        """Test chart builder returns a Figure."""
        df = pd.DataFrame(
            {
                "date": ["2026-04-01", "2026-04-02", "2026-04-08"],  # Wed, Thu, Wed
                "net_total": [50000, 55000, 52000],
            }
        )
        fig = chart_builders.build_weekday_chart(df, 50000)
        assert fig is not None
        assert len(fig.data) >= 1


class TestBuildCategoryChart:
    """Test category mix chart builder."""

    def test_groups_small_categories_into_other(self):
        """Test that categories <2% are grouped into 'Other'."""
        df = pd.DataFrame(
            {
                "category": ["Food", "Liquor", "Coffee", "Water"],
                "amount": [6000, 2500, 100, 50],  # Water=0.6%, Coffee=0.75%
            }
        )
        fig = chart_builders.build_category_chart(df, min_percent_threshold=2.0)
        # Should have 3 slices: Food, Liquor, Other (Coffee+Water)
        labels = fig.data[0].labels
        assert "Other" in labels

    def test_returns_none_for_empty_data(self):
        """Test returns None for empty DataFrame."""
        df = pd.DataFrame(columns=["category", "amount"])
        fig = chart_builders.build_category_chart(df)
        assert fig is None
