"""Tests for dynamic_report_parser helper functions and service data extraction."""

import pytest
from dynamic_report_parser import _meal_from_time


class TestMealFromTime:
    def test_before_6pm_is_lunch(self):
        assert _meal_from_time("2024-03-15 14:30:00") == "Lunch"

    def test_at_6pm_is_dinner(self):
        assert _meal_from_time("2024-03-15 18:00:00") == "Dinner"

    def test_after_6pm_is_dinner(self):
        assert _meal_from_time("2024-03-15 21:15:00") == "Dinner"

    def test_morning_is_lunch(self):
        assert _meal_from_time("2024-03-15 09:00:00") == "Lunch"

    def test_none_returns_none(self):
        assert _meal_from_time(None) is None

    def test_empty_string_returns_none(self):
        assert _meal_from_time("") is None

    def test_nan_returns_none(self):
        assert _meal_from_time("nan") is None

    def test_invalid_string_returns_none(self):
        assert _meal_from_time("not-a-time") is None


class TestDynamicReportServiceData:
    def test_parser_produces_services_key(self):
        from dynamic_report_parser import parse_dynamic_report

        csv_content = (
            "Bill Date,Bill No,Pax,Net Amount,Gross Sale,Created Date Time\n"
            "2024-03-15,B001,2,500.0,550.0,2024-03-15 12:30:00\n"
            "2024-03-15,B002,4,800.0,880.0,2024-03-15 19:00:00\n"
        )
        records, notes = parse_dynamic_report(csv_content.encode("utf-8"), "test.csv")
        assert records is not None
        assert len(records) == 1
        assert "services" in records[0]
        svc_types = [s["type"] for s in records[0]["services"]]
        assert "Lunch" in svc_types
        assert "Dinner" in svc_types

    def test_service_amounts_match_net_total(self):
        from dynamic_report_parser import parse_dynamic_report

        csv_content = (
            "Bill Date,Bill No,Pax,Net Amount,Gross Sale,Created Date Time\n"
            "2024-03-15,B001,2,500.0,550.0,2024-03-15 12:30:00\n"
            "2024-03-15,B002,4,300.0,330.0,2024-03-15 12:45:00\n"
        )
        records, _ = parse_dynamic_report(csv_content.encode("utf-8"), "test.csv")
        lunch = next(s for s in records[0]["services"] if s["type"] == "Lunch")
        assert lunch["amount"] == 800.0

    def test_no_created_datetime_column_no_services(self):
        from dynamic_report_parser import parse_dynamic_report

        csv_content = (
            "Bill Date,Bill No,Pax,Net Amount,Gross Sale\n"
            "2024-03-15,B001,2,500.0,550.0\n"
        )
        records, _ = parse_dynamic_report(csv_content.encode("utf-8"), "test.csv")
        assert records is not None
        # services key should still exist but be empty
        assert records[0].get("services") == []
