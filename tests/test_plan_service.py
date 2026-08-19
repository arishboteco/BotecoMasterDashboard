"""Tests for the suggested-plan vs actual-plan comparison."""

from datetime import date, timedelta

import pytest

from services.plan_service import build_plan_vs_actual


def _weekday_shaped_history(start: date, days: int) -> list[dict[str, object]]:
    """History with a strong weekend pattern: Mon low, Sat/Sun high."""
    by_weekday = {0: 60000, 1: 80000, 2: 85000, 3: 90000, 4: 120000, 5: 160000, 6: 150000}

    return [
        {
            "date": (start + timedelta(days=index)).isoformat(),
            "net_total": by_weekday[(start + timedelta(days=index)).weekday()],
        }
        for index in range(days)
    ]


def _split(history: list[dict[str, object]]):
    return (
        [row["date"] for row in history],
        [row["net_total"] for row in history],
    )


def test_plan_is_shaped_by_weekday_not_spread_flat() -> None:
    history = _weekday_shaped_history(date(2026, 6, 1), 74)  # through mid-Aug
    dates, values = _split(history)

    plan = build_plan_vs_actual(
        dates,
        values,
        as_of_date=date(2026, 8, 13),
        month_target=3_000_000,
    )

    assert plan["available"]

    by_weekday = {row["weekday"]: row["plan"] for row in plan["daily"]}

    # Saturday should carry a materially bigger plan than Monday.
    assert by_weekday["Sat"] > by_weekday["Mon"] * 1.5


def test_weekday_shape_survives_a_non_zero_input_index() -> None:
    """Filtered frames keep their old index; dates must not drift off values."""
    import pandas as pd

    from tabs.forecasting import build_weekday_shape

    history = _weekday_shaped_history(date(2026, 6, 1), 70)
    frame = pd.DataFrame(
        {
            "date": pd.to_datetime([row["date"] for row in history]),
            "value": [row["net_total"] for row in history],
        }
    )
    sliced = frame[frame["date"] >= "2026-06-20"]

    aligned = build_weekday_shape(
        sliced["date"].reset_index(drop=True),
        sliced["value"].tolist(),
    )
    as_passed = build_weekday_shape(sliced["date"], sliced["value"].tolist())

    assert as_passed == aligned
    # Monday is the weakest day in this fixture and must stay that way.
    assert min(as_passed, key=as_passed.get) == 0


def test_plan_sums_to_the_monthly_target() -> None:
    history = _weekday_shaped_history(date(2026, 6, 1), 74)
    dates, values = _split(history)

    plan = build_plan_vs_actual(
        dates,
        values,
        as_of_date=date(2026, 8, 13),
        month_target=3_000_000,
    )

    assert sum(row["plan"] for row in plan["daily"]) == pytest.approx(3_000_000)


def test_variance_is_measured_against_the_elapsed_share_of_plan() -> None:
    history = _weekday_shaped_history(date(2026, 6, 1), 74)
    dates, values = _split(history)
    as_of = date(2026, 8, 13)

    plan = build_plan_vs_actual(
        dates,
        values,
        as_of_date=as_of,
        month_target=3_000_000,
    )

    elapsed_plan = sum(row["plan"] for row in plan["daily"] if row["date"] <= as_of)

    assert plan["plan_to_date"] == pytest.approx(elapsed_plan)
    assert plan["variance_to_date"] == pytest.approx(
        plan["actual_to_date"] - plan["plan_to_date"]
    )
    assert plan["status"] in {"ahead", "behind", "on_track"}


def test_catchup_plan_closes_the_remaining_gap() -> None:
    history = _weekday_shaped_history(date(2026, 6, 1), 74)
    dates, values = _split(history)

    plan = build_plan_vs_actual(
        dates,
        values,
        as_of_date=date(2026, 8, 13),
        month_target=5_000_000,  # deliberately out of reach
    )

    required_total = sum(row["required"] for row in plan["catchup"])

    assert required_total == pytest.approx(plan["gap_to_target"])
    assert plan["required_forward_daily"] > plan["suggested_forward_daily"]
    assert plan["required_lift_pct"] > 0


def test_supplied_actual_total_wins_over_history_sum() -> None:
    history = _weekday_shaped_history(date(2026, 8, 1), 13)
    dates, values = _split(history)

    plan = build_plan_vs_actual(
        dates,
        values,
        as_of_date=date(2026, 8, 13),
        month_target=3_000_000,
        actual_total=1_234_567,
    )

    assert plan["actual_to_date"] == pytest.approx(1_234_567)


def test_missing_target_reports_unavailable() -> None:
    history = _weekday_shaped_history(date(2026, 8, 1), 13)
    dates, values = _split(history)

    plan = build_plan_vs_actual(
        dates,
        values,
        as_of_date=date(2026, 8, 13),
        month_target=0,
    )

    assert not plan["available"]
    assert "target" in str(plan["reason"]).lower()


def test_sparse_history_falls_back_to_a_flat_plan() -> None:
    history = [
        {"date": "2026-08-01", "net_total": 100000},
        {"date": "2026-08-02", "net_total": 120000},
    ]
    dates, values = _split(history)

    plan = build_plan_vs_actual(
        dates,
        values,
        as_of_date=date(2026, 8, 2),
        month_target=3_000_000,
    )

    assert plan["available"]
    assert plan["shape_is_flat"]

    plan_values = {round(row["plan"], 6) for row in plan["daily"]}

    assert len(plan_values) == 1


def _stub_streamlit(monkeypatch):
    """Silence Streamlit output so the renderer can run headless."""
    from tabs import analytics_sections

    class _NoopContext:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    for name in ("markdown", "caption", "dataframe", "plotly_chart", "info"):
        monkeypatch.setattr(analytics_sections.st, name, lambda *_a, **_k: None)

    monkeypatch.setattr(
        analytics_sections.st, "container", lambda *_a, **_k: _NoopContext()
    )
    monkeypatch.setattr(
        analytics_sections.st, "expander", lambda *_a, **_k: _NoopContext()
    )

    return analytics_sections


def test_render_plan_vs_actual_runs_for_mtd(monkeypatch):
    import pandas as pd

    analytics_sections = _stub_streamlit(monkeypatch)

    history = _weekday_shaped_history(date(2026, 6, 1), 74)
    df = pd.DataFrame(
        [row for row in history if str(row["date"]).startswith("2026-08")]
    ).rename(columns={"net_total": "net_total"})
    history_df = pd.DataFrame(history)

    analytics_sections.render_plan_vs_actual(
        df=df,
        analysis_period="MTD",
        end_date=date(2026, 8, 14),  # a day ahead of the data
        monthly_target=3_000_000,
        total_sales=float(df["net_total"].sum()),
        history_df=history_df,
    )


def test_render_plan_vs_actual_skips_rolling_periods(monkeypatch):
    import pandas as pd

    analytics_sections = _stub_streamlit(monkeypatch)

    history = _weekday_shaped_history(date(2026, 8, 1), 13)
    df = pd.DataFrame(history)

    # Should return without touching Streamlit at all.
    analytics_sections.render_plan_vs_actual(
        df=df,
        analysis_period="30D",
        end_date=date(2026, 8, 13),
        monthly_target=3_000_000,
        total_sales=float(df["net_total"].sum()),
    )
