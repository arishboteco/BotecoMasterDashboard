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


class TestProcessSmartUpload:
    def test_logs_parser_failure_with_context(self, monkeypatch):
        logged = []

        monkeypatch.setattr(
            smart_upload.file_detector,
            "detect_and_describe",
            lambda content, fname: ("dynamic_report", "Dynamic Report CSV"),
        )
        monkeypatch.setattr(smart_upload.file_detector, "is_importable", lambda k: True)
        monkeypatch.setattr(smart_upload.file_detector, "is_skippable", lambda k: False)
        monkeypatch.setattr(
            smart_upload.dynamic_report_parser,
            "parse_dynamic_report",
            lambda content, fname: (_ for _ in ()).throw(ValueError("boom")),
        )
        monkeypatch.setattr(
            smart_upload.logger,
            "exception",
            lambda msg, *args: logged.append(msg % args),
        )

        result = smart_upload.process_smart_upload([("dyn.csv", b"x")], location_id=1)

        assert result.files[0].error == "boom"
        assert any("dynamic_report" in line for line in logged)

    def test_order_summary_only_adds_uncovered_days(self, monkeypatch):
        monkeypatch.setattr(
            smart_upload.file_detector,
            "detect_and_describe",
            lambda content, fname: (
                "item_order_details"
                if fname.endswith(".xlsx")
                else "order_summary_csv",
                "label",
            ),
        )
        monkeypatch.setattr(smart_upload.file_detector, "is_importable", lambda k: True)
        monkeypatch.setattr(smart_upload.file_detector, "is_skippable", lambda k: False)
        monkeypatch.setattr(
            smart_upload.pos_parser,
            "parse_item_order_details",
            lambda content, fname: [
                {
                    "date": "2026-04-01",
                    "file_type": "item_order_details",
                    "net_total": 100.0,
                    "gross_total": 100.0,
                    "covers": 1,
                }
            ],
        )
        monkeypatch.setattr(
            smart_upload,
            "_parse_order_summary_csv",
            lambda content, fname: (
                [
                    {
                        "date": "2026-04-01",
                        "file_type": "order_summary_csv",
                        "net_total": 50.0,
                        "gross_total": 50.0,
                        "covers": 1,
                    },
                    {
                        "date": "2026-04-02",
                        "file_type": "order_summary_csv",
                        "net_total": 70.0,
                        "gross_total": 70.0,
                        "covers": 1,
                    },
                ],
                [],
            ),
        )
        monkeypatch.setattr(
            smart_upload.pos_parser,
            "group_fragments_by_date",
            lambda fragments: {
                d: [f for f in fragments if f["date"] == d]
                for d in sorted({f["date"] for f in fragments})
            },
        )
        monkeypatch.setattr(
            smart_upload.pos_parser,
            "merge_upload_fragments",
            lambda frags: dict(frags[0]),
        )
        monkeypatch.setattr(
            smart_upload.pos_parser, "validate_data", lambda data: (True, [])
        )
        monkeypatch.setattr(
            smart_upload.database,
            "get_all_locations",
            lambda: [{"id": 1, "name": "Boteco - Indiqube"}],
        )

        result = smart_upload.process_smart_upload(
            [("item.xlsx", b"x"), ("orders.csv", b"x")],
            location_id=1,
        )

        days = result.location_results.get(1, [])
        dates = [d.date for d in days]
        assert dates == ["2026-04-01", "2026-04-02"]
