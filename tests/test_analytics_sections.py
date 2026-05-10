"""Tests for analytics section rendering safeguards."""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from tabs import analytics_sections


class _NoopContext:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_render_revenue_breakdown_handles_empty_weekday_agg(monkeypatch):
    start = date(2026, 4, 1)
    rows = []
    for i in range(7):
        rows.append(
            {
                "date": start + timedelta(days=i),
                "net_total": 0.0,
            }
        )
    df = pd.DataFrame(rows)

    monkeypatch.setattr(
        analytics_sections.database,
        "get_category_sales_for_date_range",
        lambda *_args, **_kwargs: [],
    )
    monkeypatch.setattr(
        analytics_sections.scope,
        "sum_location_monthly_targets",
        lambda _loc_ids: 0,
    )
    monkeypatch.setattr(analytics_sections.st, "markdown", lambda *_a, **_k: None)
    monkeypatch.setattr(analytics_sections.st, "caption", lambda *_a, **_k: None)
    monkeypatch.setattr(analytics_sections.st, "dataframe", lambda *_a, **_k: None)
    monkeypatch.setattr(analytics_sections.st, "plotly_chart", lambda *_a, **_k: None)
    monkeypatch.setattr(analytics_sections.st, "expander", lambda *_a, **_k: _NoopContext())

    analytics_sections.render_revenue_breakdown(
        report_loc_ids=[1],
        start_str="2026-04-01",
        end_str="2026-04-07",
        df=df,
        start_date=start,
    )


def test_build_action_cards_flags_target_gap():
    current_df = pd.DataFrame(
        [
            {"date": "2026-05-01", "net_total": 90000.0, "covers": 60, "apc": 1500.0},
            {"date": "2026-05-02", "net_total": 85000.0, "covers": 58, "apc": 1465.0},
        ]
    )
    prior_df = pd.DataFrame(
        [
            {"date": "2026-04-29", "net_total": 120000.0, "covers": 72, "apc": 1666.0},
            {"date": "2026-04-30", "net_total": 115000.0, "covers": 70, "apc": 1642.0},
        ]
    )

    cards = analytics_sections._build_action_cards(
        current_df=current_df,
        prior_df=prior_df,
        monthly_target=10_00_000.0,
        forecast_total=6_50_000.0,
    )

    assert cards
    assert any("Target" in card["title"] for card in cards)


def test_build_action_cards_flags_apc_covers_divergence():
    current_df = pd.DataFrame(
        [
            {"date": "2026-05-01", "net_total": 150000.0, "covers": 100, "apc": 1500.0},
            {"date": "2026-05-02", "net_total": 152000.0, "covers": 104, "apc": 1461.0},
        ]
    )
    prior_df = pd.DataFrame(
        [
            {"date": "2026-04-29", "net_total": 149000.0, "covers": 82, "apc": 1817.0},
            {"date": "2026-04-30", "net_total": 151000.0, "covers": 84, "apc": 1798.0},
        ]
    )

    cards = analytics_sections._build_action_cards(
        current_df=current_df,
        prior_df=prior_df,
        monthly_target=0.0,
        forecast_total=0.0,
    )

    assert cards
    assert any("APC" in card["title"] for card in cards)


def test_build_weekpart_insight_uses_friday_as_weekend():
    df = pd.DataFrame(
        [
            {"date": "2026-05-07", "covers": 40},
            {"date": "2026-05-08", "covers": 70},
            {"date": "2026-05-09", "covers": 80},
            {"date": "2026-05-10", "covers": 90},
        ]
    )

    insight = analytics_sections._build_weekpart_insight(df)

    assert insight["weekday_count"] == 1
    assert insight["weekend_count"] == 3
    assert insight["weekday_avg"] == 40.0
    assert insight["weekend_avg"] == 80.0


def test_build_weekpart_insight_commentary_weekend_led():
    df = pd.DataFrame(
        [
            {"date": "2026-05-05", "covers": 40},
            {"date": "2026-05-06", "covers": 45},
            {"date": "2026-05-09", "covers": 90},
            {"date": "2026-05-10", "covers": 95},
        ]
    )

    insight = analytics_sections._build_weekpart_insight(df)

    assert insight["status"] == "ok"
    assert insight["delta_pct"] > 0
    assert "Weekend-led pattern" in insight["commentary"]


def test_build_weekpart_insight_insufficient_data_when_bucket_missing():
    df = pd.DataFrame(
        [
            {"date": "2026-05-05", "covers": 50},
            {"date": "2026-05-06", "covers": 55},
        ]
    )

    insight = analytics_sections._build_weekpart_insight(df)

    assert insight["status"] == "insufficient"
    assert insight["commentary"] == "Insufficient data for comparison"


def test_render_driver_analysis_renders_covers_as_line(monkeypatch):
    df = pd.DataFrame(
        [
            {"date": "2026-05-05", "covers": 40, "net_total": 40000.0},
            {"date": "2026-05-06", "covers": 50, "net_total": 50000.0},
        ]
    )
    captured = []

    monkeypatch.setattr(analytics_sections.st, "markdown", lambda *_a, **_k: None)
    monkeypatch.setattr(analytics_sections.st, "caption", lambda *_a, **_k: None)
    monkeypatch.setattr(analytics_sections.st, "toggle", lambda *_a, **_k: False)
    monkeypatch.setattr(
        analytics_sections.st,
        "columns",
        lambda *_a, **_k: (_NoopContext(), _NoopContext()),
    )
    monkeypatch.setattr(analytics_sections.st, "container", lambda *_a, **_k: _NoopContext())
    monkeypatch.setattr(
        analytics_sections.st,
        "plotly_chart",
        lambda fig, **_k: captured.append(fig),
    )

    analytics_sections.render_driver_analysis(
        df=df,
        df_raw=pd.DataFrame(),
        multi_analytics=False,
    )

    covers_fig = captured[0]
    assert covers_fig.data[0].type == "scatter"
    assert covers_fig.data[0].mode == "lines+markers"


def test_build_weekly_weekend_lift_returns_week_rows():
    df = pd.DataFrame(
        [
            {"date": "2026-05-04", "covers": 50},
            {"date": "2026-05-05", "covers": 60},
            {"date": "2026-05-06", "covers": 70},
            {"date": "2026-05-07", "covers": 80},
            {"date": "2026-05-08", "covers": 100},
            {"date": "2026-05-09", "covers": 110},
            {"date": "2026-05-10", "covers": 120},
            {"date": "2026-05-11", "covers": 55},
            {"date": "2026-05-12", "covers": 65},
            {"date": "2026-05-13", "covers": 75},
            {"date": "2026-05-14", "covers": 85},
            {"date": "2026-05-15", "covers": 95},
            {"date": "2026-05-16", "covers": 105},
            {"date": "2026-05-17", "covers": 115},
        ]
    )

    out = analytics_sections._build_weekly_weekend_lift(df)

    assert len(out) == 2
    assert "lift_pct" in out.columns


def test_weekly_lift_commentary_uses_period_over_period_signal():
    lift_df = pd.DataFrame(
        [
            {"week_start": pd.Timestamp("2026-05-04"), "lift_pct": 30.0},
            {"week_start": pd.Timestamp("2026-05-11"), "lift_pct": 38.5},
        ]
    )

    text = analytics_sections._weekly_lift_commentary(lift_df)

    assert "improving" in text


def test_build_weekly_covers_trend_returns_avg_daily_series():
    df = pd.DataFrame(
        [
            {"date": "2026-05-04", "covers": 70},
            {"date": "2026-05-05", "covers": 80},
            {"date": "2026-05-06", "covers": 90},
            {"date": "2026-05-12", "covers": 100},
            {"date": "2026-05-13", "covers": 110},
        ]
    )

    out = analytics_sections._build_weekly_covers_trend(df)

    assert len(out) == 2
    assert "avg_daily_covers" in out.columns
    assert "days_count" in out.columns


def test_weekly_covers_commentary_reports_increasing_trend():
    weekly_df = pd.DataFrame(
        [
            {
                "week_start": pd.Timestamp("2026-05-04"),
                "avg_daily_covers": 80.0,
            },
            {
                "week_start": pd.Timestamp("2026-05-11"),
                "avg_daily_covers": 92.0,
            },
        ]
    )

    text = analytics_sections._weekly_covers_commentary(weekly_df)

    assert "increasing" in text
