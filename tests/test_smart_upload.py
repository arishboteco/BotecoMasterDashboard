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
    def test_requires_dynamic_report_for_supabase_save(self, monkeypatch):
        """save_smart_upload_results only persists Dynamic Report CSVs (Supabase)."""
        monkeypatch.setattr(smart_upload.database, "use_supabase", lambda: True)
        monkeypatch.setattr(smart_upload.database, "get_supabase_client", lambda: object())

        result = SmartUploadResult(
            files=[
                FileResult(
                    filename="orders.csv",
                    kind="order_summary_csv",
                    kind_label="Order Summary",
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

        assert saved == 0
        assert skipped == 1
        assert any("No Dynamic Report" in m for m in messages)


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
