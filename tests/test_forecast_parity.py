"""Parity tests for Report and Analytics month-end forecasts."""

from datetime import date, timedelta

import pandas as pd
import pytest

import sheet_reports
from services.forecast_service import calculate_month_end_forecast
from tabs.analytics_sections import _calculate_period_forecast


def _daily_history() -> list[dict[str, object]]:
    values = [
        15000,
        14000,
        16000,
        22000,
        21000,
        13000,
        15000,
        14500,
        16500,
        23000,
        22500,
        13500,
        15500,
        17000,
    ]
    return [
        {"date": f"2026-04-{index:02d}", "net_total": value}
        for index, value in enumerate(values, start=1)
    ]


def test_report_and_analytics_mtd_use_the_same_forecast() -> None:
    history = _daily_history()
    total_sales = float(sum(row["net_total"] for row in history))
    analytics_df = pd.DataFrame(history)

    result = _calculate_period_forecast(
        analytics_df,
        "MTD",
        date(2026, 4, 1),
        date(2026, 4, 14),
        total_sales,
    )
    report_result = sheet_reports.compute_forecast_metrics(
        {
            "date": "2026-04-14",
            "mtd_net_sales": total_sales,
            "mtd_target": 450000,
        },
        daily_sales_history=history,
    )

    assert result["headline_label"] == "Forecast Month-End"
    assert result["forecast_days"] == 16
    assert result["forecast"]
    assert result["headline_value"] == pytest.approx(
        report_result["forecast_month_end_sales"]
    )


def test_mtd_forecast_ignores_rows_after_the_as_of_date() -> None:
    history = _daily_history()
    history.append({"date": "2026-04-30", "net_total": 999999})
    as_of_history = history[:-1]
    total_sales = float(sum(row["net_total"] for row in as_of_history))

    report_result = sheet_reports.compute_forecast_metrics(
        {
            "date": "2026-04-14",
            "mtd_net_sales": total_sales,
            "mtd_target": 450000,
        },
        daily_sales_history=history,
    )
    expected_result = sheet_reports.compute_forecast_metrics(
        {
            "date": "2026-04-14",
            "mtd_net_sales": total_sales,
            "mtd_target": 450000,
        },
        daily_sales_history=as_of_history,
    )

    assert report_result["forecast_month_end_sales"] == pytest.approx(
        expected_result["forecast_month_end_sales"]
    )


def test_rolling_period_projection_reports_forward_sales_only() -> None:
    analytics_df = pd.DataFrame(_daily_history())
    total_sales = float(analytics_df["net_total"].sum())

    result = _calculate_period_forecast(
        analytics_df,
        "30D",
        date(2026, 3, 16),
        date(2026, 4, 14),
        total_sales,
    )

    assert result["forecast_days"] == 7
    assert result["headline_label"] == "Next 7 Days (Forecast)"
    assert not result["is_month_end"]
    # Forward-only: the selected window's actual sales are not folded in.
    assert result["headline_value"] == pytest.approx(result["forward_total"])
    assert result["headline_value"] < total_sales


def test_mtd_forecast_anchors_on_last_data_date_not_end_date() -> None:
    """Sales land a day in arrears; today must not shorten the forecast."""
    history = _daily_history()
    total_sales = float(sum(row["net_total"] for row in history))
    analytics_df = pd.DataFrame(history)

    # Data runs to 14 Apr; the selected window ends "today", 15 Apr.
    lagging = _calculate_period_forecast(
        analytics_df,
        "MTD",
        date(2026, 4, 1),
        date(2026, 4, 15),
        total_sales,
    )
    aligned = _calculate_period_forecast(
        analytics_df,
        "MTD",
        date(2026, 4, 1),
        date(2026, 4, 14),
        total_sales,
    )

    assert lagging["as_of_date"] == date(2026, 4, 14)
    assert lagging["forecast_days"] == aligned["forecast_days"] == 16
    assert lagging["headline_value"] == pytest.approx(aligned["headline_value"])


def test_analytics_matches_report_when_data_lags_today() -> None:
    """The two tabs must agree on the day after the last upload."""
    history = _daily_history()
    total_sales = float(sum(row["net_total"] for row in history))

    analytics = _calculate_period_forecast(
        pd.DataFrame(history),
        "MTD",
        date(2026, 4, 1),
        date(2026, 4, 15),  # today, one day ahead of the data
        total_sales,
    )
    report = sheet_reports.compute_forecast_metrics(
        {
            "date": "2026-04-14",
            "mtd_net_sales": total_sales,
            "mtd_target": 450000,
        },
        daily_sales_history=history,
    )

    assert analytics["headline_value"] == pytest.approx(
        report["forecast_month_end_sales"]
    )


def test_trailing_history_crosses_the_month_boundary() -> None:
    """Early-month forecasts should learn from the previous month, not 3 points."""
    start = date(2026, 3, 1)
    values = [15000, 14000, 16000, 22000, 21000, 13000, 15000]
    history = [
        {
            "date": (start + timedelta(days=index)).isoformat(),
            "net_total": values[index % len(values)],
        }
        for index in range(38)  # 1 Mar through 7 Apr
    ]

    as_of = date(2026, 4, 3)
    month_actual = sum(
        row["net_total"]
        for row in history
        if row["date"] <= as_of.isoformat() and row["date"] >= "2026-04-01"
    )

    result = calculate_month_end_forecast(
        [row["date"] for row in history if row["date"] <= as_of.isoformat()],
        [row["net_total"] for row in history if row["date"] <= as_of.isoformat()],
        as_of_date=as_of,
        actual_total=month_actual,
    )

    # Model sees the full trailing window; the MTD actual stays month-scoped.
    assert result["model_points"] == 34
    assert result["history_points"] == 3
    assert result["method"] == "weighted"
    assert result["forecast"][0]["metadata"]["weekday_coverage"] == 7
