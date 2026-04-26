"""Tests for upload result dataclasses."""

from uploads.models import DayResult, FileResult, SmartUploadResult


def test_file_result_construction_defaults():
    result = FileResult(
        filename="orders.csv",
        kind="order_summary_csv",
        kind_label="Order Summary",
        importable=True,
    )

    assert result.filename == "orders.csv"
    assert result.notes == []
    assert result.error is None
    assert result.content is None


def test_day_result_construction_defaults():
    day = DayResult(
        date="2026-04-02",
        merged={"net_total": 1000.0},
    )

    assert day.date == "2026-04-02"
    assert day.merged["net_total"] == 1000.0
    assert day.source_kinds == []
    assert day.errors == []
    assert day.warnings == []


def test_smart_upload_result_construction_defaults():
    day = DayResult(date="2026-04-02", merged={"net_total": 1000.0})
    file_result = FileResult(
        filename="orders.csv",
        kind="order_summary_csv",
        kind_label="Order Summary",
        importable=True,
    )
    result = SmartUploadResult(files=[file_result], days=[day])

    assert result.files == [file_result]
    assert result.days == [day]
    assert result.global_notes == []
    assert result.location_results == {}
