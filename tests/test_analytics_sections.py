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
