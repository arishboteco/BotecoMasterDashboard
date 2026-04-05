"""Forecast/status/summary tests for sheet reports."""

import sheet_reports


class TestForecastMetrics:
    def test_forecast_metrics_mid_month(self):
        result = sheet_reports.compute_forecast_metrics(
            {
                "date": "2026-04-15",
                "mtd_net_sales": 225000,
                "mtd_target": 450000,
            }
        )
        assert result["days_in_month"] == 30
        assert result["elapsed_days"] == 15
        assert round(result["forecast_month_end_sales"], 2) == 450000.00
        assert round(result["forecast_target_pct"], 2) == 100.00

    def test_forecast_handles_missing_target(self):
        result = sheet_reports.compute_forecast_metrics(
            {"date": "2026-04-15", "mtd_net_sales": 225000, "mtd_target": 0}
        )
        assert result["forecast_month_end_sales"] > 0
        assert result["forecast_target_pct"] is None
        assert result["forecast_gap_amount"] is None


class TestMetricStatuses:
    def test_target_status_red_under_85(self):
        status = sheet_reports.status_from_threshold(
            74,
            green_min=100,
            amber_min=85,
            higher_is_better=True,
        )
        assert status["status"] == "red"

    def test_forecast_status_amber_between_95_and_100(self):
        status = sheet_reports.status_from_threshold(
            97,
            green_min=100,
            amber_min=95,
            higher_is_better=True,
        )
        assert status["status"] == "amber"

    def test_discount_status_green_at_or_below_5(self):
        status = sheet_reports.status_from_threshold(
            4.9,
            green_max=5,
            amber_max=8,
            higher_is_better=False,
        )
        assert status["status"] == "green"


class TestVerboseSummary:
    def test_verbose_summary_contains_forecast_and_action(self):
        result = sheet_reports.build_verbose_daily_summary(
            {
                "date": "2026-04-15",
                "net_total": 18000,
                "target": 20000,
                "mtd_net_sales": 225000,
                "mtd_target": 450000,
                "discount": 1200,
                "gross_total": 22000,
                "apc": 410,
                "apc_baseline_7d": 460,
                "previous_day_net_total": 20000,
                "same_weekday_last_week_net_total": 19500,
            }
        )
        assert "Forecast month-end" in result
        assert "Suggested action" in result
        assert len(result.split("\n")) >= 5

    def test_verbose_summary_handles_missing_benchmarks(self):
        result = sheet_reports.build_verbose_daily_summary(
            {
                "date": "2026-04-02",
                "net_total": 9000,
                "target": 12000,
                "mtd_net_sales": 18000,
                "mtd_target": 360000,
            }
        )
        assert "benchmark unavailable" in result.lower()
