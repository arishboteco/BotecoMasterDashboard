"""Parity tests for Report and Analytics month-end forecasts."""

from datetime import date

import pandas as pd
import pytest

import sheet_reports
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

    forecast, analytics_total, remaining_days, label = _calculate_period_forecast(
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

    assert label == "Forecast Month-End"
    assert remaining_days == 16
    assert forecast
    assert analytics_total == pytest.approx(report_result["forecast_month_end_sales"])


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


def test_rolling_period_projection_has_a_non_monthly_label() -> None:
    analytics_df = pd.DataFrame(_daily_history())
    total_sales = float(analytics_df["net_total"].sum())

    _forecast, _total, forecast_days, label = _calculate_period_forecast(
        analytics_df,
        "30D",
        date(2026, 3, 16),
        date(2026, 4, 14),
        total_sales,
    )

    assert forecast_days == 7
    assert label == "Projected Total + Next 7 Days"
