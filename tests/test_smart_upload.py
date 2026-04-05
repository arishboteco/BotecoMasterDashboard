"""Tests for smart_upload save metadata behavior."""

from smart_upload import DayResult, FileResult, SmartUploadResult
import smart_upload


class TestPrimaryFileType:
    def test_prefers_dynamic_over_other_sources(self):
        kinds = ["flash_report", "item_order_details", "dynamic_report"]
        assert smart_upload._primary_file_type(kinds) == "dynamic_report"

    def test_falls_back_to_item_order_details(self):
        assert smart_upload._primary_file_type([]) == "item_order_details"


class TestSaveSmartUploadResults:
    def test_uses_day_source_kinds_for_upload_history(self, monkeypatch):
        saved_summaries = []
        upload_records = []

        monkeypatch.setattr(
            smart_upload.pos_parser,
            "calculate_derived_metrics",
            lambda data: data,
        )
        monkeypatch.setattr(
            smart_upload.pos_parser,
            "calculate_mtd_metrics",
            lambda *args, **kwargs: {},
        )
        monkeypatch.setattr(
            smart_upload.database,
            "save_daily_summary",
            lambda location_id, data: saved_summaries.append((location_id, data)),
        )
        monkeypatch.setattr(
            smart_upload.database,
            "save_upload_record",
            lambda location_id, date, filename, file_type, uploaded_by: (
                upload_records.append(
                    {
                        "location_id": location_id,
                        "date": date,
                        "filename": filename,
                        "file_type": file_type,
                        "uploaded_by": uploaded_by,
                    }
                )
            ),
        )

        result = SmartUploadResult(
            files=[
                FileResult(
                    filename="orders.csv",
                    kind="order_summary_csv",
                    kind_label="Order Summary",
                    importable=True,
                ),
                FileResult(
                    filename="flash.xlsx",
                    kind="flash_report",
                    kind_label="Flash",
                    importable=True,
                ),
                FileResult(
                    filename="timing.xlsx",
                    kind="timing_report",
                    kind_label="Timing",
                    importable=True,
                ),
            ],
            days=[
                DayResult(
                    date="2026-04-02",
                    merged={
                        "date": "2026-04-02",
                        "gross_total": 1000.0,
                        "net_total": 1000.0,
                    },
                    source_kinds=["order_summary_csv", "flash_report"],
                    errors=[],
                )
            ],
        )

        saved, skipped, messages = smart_upload.save_smart_upload_results(
            result,
            location_id=7,
            uploaded_by="qa",
            monthly_target=5000000.0,
            daily_target=166667.0,
        )

        assert saved == 1
        assert skipped == 0
        assert messages == ["Saved 2026-04-02."]
        assert len(saved_summaries) == 1
        assert len(upload_records) == 1
        assert upload_records[0]["file_type"] == "order_summary_csv"
        assert upload_records[0]["filename"] == "orders.csv, flash.xlsx"
