"""Tests for pure analytics tab helper logic."""

from datetime import date, timedelta

import pandas as pd
import pytest

from tabs.analytics_logic import (
    build_daily_view_table,
    build_zomato_economics,
    classify_platform_cost_coverage,
    resolve_period_window,
)


class TestResolvePeriodWindow:
    def test_custom_period_requires_dates(self):
        try:
            resolve_period_window("Custom")
        except ValueError:
            return
        raise AssertionError("Expected ValueError for missing custom dates")

    def test_custom_period_returns_same_length_prior(self):
        start, end, prior_start, prior_end, period_key = resolve_period_window(
            "Custom",
            custom_start=date(2026, 4, 1),
            custom_end=date(2026, 4, 10),
        )

        assert start == date(2026, 4, 1)
        assert end == date(2026, 4, 10)
        assert prior_end == date(2026, 3, 31)
        assert prior_start == date(2026, 3, 22)
        assert period_key == "custom"

    def test_last_7_days_prior_has_exactly_7_days(self):
        start, end, prior_start, prior_end, period_key = resolve_period_window(
            "7D"
        )
        current_days = (end - start).days + 1
        prior_days = (prior_end - prior_start).days + 1

        assert current_days == 7
        assert prior_days == 7
        assert prior_end == start - timedelta(days=1)
        assert (prior_end - prior_start).days == 6

    def test_last_30_days_prior_has_exactly_30_days(self):
        start, end, prior_start, prior_end, period_key = resolve_period_window(
            "30D"
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
            "MTD"
        )
        current_days = (end - start).days + 1
        prior_days = (prior_end - prior_start).days + 1

        assert current_days == prior_days
        assert prior_end == start - timedelta(days=1)
        assert prior_start == prior_end - timedelta(days=current_days - 1)

    def test_qtd_prior_matches_current_span(self):
        start, end, prior_start, prior_end, period_key = resolve_period_window("QTD")

        current_days = (end - start).days + 1
        prior_days = (prior_end - prior_start).days + 1

        assert period_key == "qtd"
        assert current_days == prior_days
        assert prior_end == start - timedelta(days=1)


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


class TestZomatoEconomics:
    def test_builds_platform_cost_coverage_metrics(self):
        result = build_zomato_economics(
            zomato_pay_sales=10_00_000,
            fee_pct=5.9,
            contribution_margin_pct=60,
            incremental_sales=2_50_000,
            target_coverage_ratio=1.5,
        )

        assert result["platform_cost"] == pytest.approx(59_000)
        assert result["incremental_contribution"] == pytest.approx(1_50_000)
        assert result["coverage_ratio"] == pytest.approx(2.542, abs=0.001)
        assert result["break_even_incremental_sales"] == pytest.approx(98_333.33, abs=0.01)
        assert result["target_incremental_sales"] == pytest.approx(1_47_500)

    def test_zero_cost_returns_no_ratio_or_required_sales(self):
        result = build_zomato_economics(
            zomato_pay_sales=0,
            fee_pct=5.9,
            contribution_margin_pct=60,
            incremental_sales=50_000,
            target_coverage_ratio=1.5,
        )

        assert result["platform_cost"] == 0
        assert result["coverage_ratio"] is None
        assert result["break_even_incremental_sales"] == 0
        assert result["target_incremental_sales"] == 0

    def test_classifies_coverage_ratio_for_decision_copy(self):
        assert classify_platform_cost_coverage(None)["label"] == "No Zomato cost"
        assert classify_platform_cost_coverage(0.8)["label"] == "Losing money"
        assert classify_platform_cost_coverage(1.2)["label"] == "Barely justified"
        assert classify_platform_cost_coverage(2.0)["label"] == "Healthy"
        assert classify_platform_cost_coverage(3.0)["label"] == "Strong channel"
