"""Tests for pure analytics tab helper logic."""

from datetime import date, timedelta

import pandas as pd

from tabs.analytics_logic import build_daily_view_table, resolve_period_window


class TestResolvePeriodWindow:
    def test_custom_period_requires_dates(self):
        try:
            resolve_period_window("Custom")
        except ValueError:
            return
        raise AssertionError("Expected ValueError for missing custom dates")

    def test_custom_period_returns_no_prior(self):
        start, end, prior_start, prior_end, period_key = resolve_period_window(
            "Custom",
            custom_start=date(2026, 4, 1),
            custom_end=date(2026, 4, 10),
        )

        assert start == date(2026, 4, 1)
        assert end == date(2026, 4, 10)
        assert prior_start is None
        assert prior_end is None
        assert period_key is None

    def test_last_7_days_prior_has_exactly_7_days(self):
        start, end, prior_start, prior_end, period_key = resolve_period_window(
            "Last 7 Days"
        )
        current_days = (end - start).days + 1
        prior_days = (prior_end - prior_start).days + 1

        assert current_days == 7
        assert prior_days == 7
        assert prior_end == start - timedelta(days=1)
        assert (prior_end - prior_start).days == 6

    def test_last_30_days_prior_has_exactly_30_days(self):
        start, end, prior_start, prior_end, period_key = resolve_period_window(
            "Last 30 Days"
        )
        current_days = (end - start).days + 1
        prior_days = (prior_end - prior_start).days + 1

        assert current_days == 30
        assert prior_days == 30
        assert prior_end == start - timedelta(days=1)
        assert (prior_end - prior_start).days == 29

    def test_this_week_prior_is_last_week_exact(self):
        start, end, prior_start, prior_end, period_key = resolve_period_window(
            "This Week"
        )
        current_days = (end - start).days + 1
        prior_days = (prior_end - prior_start).days + 1

        assert current_days == prior_days
        assert prior_end == start - timedelta(days=1)
        assert prior_start == prior_end - timedelta(days=current_days - 1)

    def test_this_month_prior_is_last_month_exact(self):
        start, end, prior_start, prior_end, period_key = resolve_period_window(
            "This Month"
        )
        current_days = (end - start).days + 1
        prior_days = (prior_end - prior_start).days + 1

        assert current_days == prior_days
        assert prior_end == start - timedelta(days=1)
        assert prior_start == prior_end - timedelta(days=current_days - 1)


class TestBuildDailyViewTable:
    def test_builds_single_location_view(self):
        df = pd.DataFrame(
            [
                {
                    "date": "2026-04-01",
                    "covers": 100,
                    "net_total": 12345.67,
                    "target": 20000,
                    "pct_target": 61.72,
                }
            ]
        )

        out = build_daily_view_table(df, pd.DataFrame(), multi_analytics=False)

        assert list(out.columns) == [
            "date",
            "covers",
            "net_total",
            "target",
            "pct_target",
        ]
        assert out.iloc[0]["covers"] == "100"
        assert "₹" in out.iloc[0]["net_total"]

    def test_builds_multi_location_view(self):
        df_raw = pd.DataFrame(
            [
                {
                    "date": "2026-04-01",
                    "Outlet": "A",
                    "covers": 40,
                    "net_total": 5000,
                    "target": 6000,
                    "pct_target": 83.33,
                },
                {
                    "date": "2026-04-01",
                    "Outlet": "B",
                    "covers": 60,
                    "net_total": 7000,
                    "target": 8000,
                    "pct_target": 87.5,
                },
            ]
        )

        out = build_daily_view_table(pd.DataFrame(), df_raw, multi_analytics=True)

        assert "Outlet" in out.columns
        assert len(out) == 3
        assert out.iloc[-1]["date"] == "TOTAL"

    def test_returns_empty_when_multi_without_raw_rows(self):
        out = build_daily_view_table(
            pd.DataFrame(), pd.DataFrame(), multi_analytics=True
        )
        assert out.empty
