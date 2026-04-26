"""Tests for smart_upload save metadata behavior."""

import smart_upload
from smart_upload import DayResult, FileResult, SmartUploadResult


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

        _day = DayResult(
            date="2026-04-02",
            merged={
                "date": "2026-04-02",
                "gross_total": 1000.0,
                "net_total": 1000.0,
            },
            source_kinds=["order_summary_csv", "flash_report"],
            errors=[],
        )
        result = SmartUploadResult(
            files=[
                FileResult(
                    filename="orders.csv",
                    kind="order_summary_csv",
                    kind_label="Order Summary",
                    importable=True,
                ),
            ],
            days=[_day],
            location_results={7: [_day]},
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
        monkeypatch.setattr(
            smart_upload.database,
            "get_all_locations",
            lambda: [{"id": 1, "name": "Boteco - Indiqube"}],
        )

        result = smart_upload.process_smart_upload([("dyn.csv", b"x")], location_id=1)

        assert result.files[0].error == "boom"
        assert any("dynamic_report" in line for line in logged)

    def test_order_summary_only_adds_uncovered_days(self, monkeypatch):
        monkeypatch.setattr(
            smart_upload.file_detector,
            "detect_and_describe",
            lambda content, fname: (
                "item_order_details" if fname.endswith(".xlsx") else "order_summary_csv",
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
            "parse_order_summary_csv",
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
        monkeypatch.setattr(smart_upload.pos_parser, "validate_data", lambda data: (True, [], []))
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


class TestParseOrderSummaryCsv:
    def test_accepts_successorder_status_rows(self):
        content = ("date,my_amount,status,payment_type\n2026-04-01,100,SuccessOrder,GPay\n").encode(
            "utf-8"
        )

        parsed, notes = smart_upload.parse_order_summary_csv(content, "orders.csv")

        assert notes == []
        assert parsed is not None
        assert len(parsed) == 1
        assert parsed[0]["date"] == "2026-04-01"
        assert parsed[0]["net_total"] == 100.0
        assert parsed[0]["gpay_sales"] == 100.0

    def test_accepts_success_order_status_with_space(self):
        content = (
            "date,my_amount,status,payment_type\n2026-04-01,120,Success Order,Card\n"
        ).encode("utf-8")

        parsed, notes = smart_upload.parse_order_summary_csv(content, "orders.csv")

        assert notes == []
        assert parsed is not None
        assert len(parsed) == 1
        assert parsed[0]["date"] == "2026-04-01"
        assert parsed[0]["net_total"] == 120.0
        assert parsed[0]["card_sales"] == 120.0

    def test_accepts_success_order_status_with_hyphen_and_case(self):
        content = ("date,my_amount,status,payment_type\n2026-04-01,90,SUCCESS-ORDER,Cash\n").encode(
            "utf-8"
        )

        parsed, notes = smart_upload.parse_order_summary_csv(content, "orders.csv")

        assert notes == []
        assert parsed is not None
        assert len(parsed) == 1
        assert parsed[0]["date"] == "2026-04-01"
        assert parsed[0]["net_total"] == 90.0
        assert parsed[0]["cash_sales"] == 90.0

    def test_rejects_complimentary_status_even_if_success_like(self):
        content = (
            "date,my_amount,status,payment_type\n2026-04-01,90,Success Complimentary,Cash\n"
        ).encode("utf-8")

        parsed, notes = smart_upload.parse_order_summary_csv(content, "orders.csv")

        assert notes == []
        assert parsed is None


class TestRoutingAndMergeExtraction:
    def test_known_restaurant_maps_to_correct_location(self, monkeypatch):
        monkeypatch.setattr(
            smart_upload.file_detector, "detect_and_describe", lambda c, f: ("dynamic_report", "d")
        )
        monkeypatch.setattr(smart_upload.file_detector, "is_importable", lambda k: True)
        monkeypatch.setattr(smart_upload.file_detector, "is_skippable", lambda k: False)
        monkeypatch.setattr(
            smart_upload.dynamic_report_parser,
            "parse_dynamic_report",
            lambda c, f: (
                [
                    {
                        "date": "2026-04-01",
                        "restaurant": "Boteco",
                        "file_type": "dynamic_report",
                        "net_total": 100.0,
                        "gross_total": 100.0,
                        "covers": 1,
                    }
                ],
                [],
            ),
        )
        monkeypatch.setattr(
            smart_upload.database,
            "get_all_locations",
            lambda: [{"id": 11, "name": "Boteco - Indiqube"}],
        )
        monkeypatch.setattr(
            smart_upload.pos_parser,
            "group_fragments_by_date",
            lambda fragments: {"2026-04-01": fragments},
        )
        monkeypatch.setattr(
            smart_upload.pos_parser, "merge_upload_fragments", lambda frags: dict(frags[0])
        )
        monkeypatch.setattr(smart_upload.pos_parser, "validate_data", lambda data: (True, [], []))

        result = smart_upload.process_smart_upload([("dyn.csv", b"x")], location_id=99)

        assert 11 in result.location_results
        assert [d.date for d in result.location_results[11]] == ["2026-04-01"]

    def test_unknown_restaurant_is_skipped_with_note(self, monkeypatch):
        monkeypatch.setattr(
            smart_upload.file_detector, "detect_and_describe", lambda c, f: ("dynamic_report", "d")
        )
        monkeypatch.setattr(smart_upload.file_detector, "is_importable", lambda k: True)
        monkeypatch.setattr(smart_upload.file_detector, "is_skippable", lambda k: False)
        monkeypatch.setattr(
            smart_upload.dynamic_report_parser,
            "parse_dynamic_report",
            lambda c, f: (
                [
                    {
                        "date": "2026-04-01",
                        "restaurant": "Unknown Outlet",
                        "file_type": "dynamic_report",
                    }
                ],
                [],
            ),
        )
        monkeypatch.setattr(
            smart_upload.database,
            "get_all_locations",
            lambda: [{"id": 11, "name": "Boteco - Indiqube"}],
        )

        result = smart_upload.process_smart_upload([("dyn.csv", b"x")], location_id=11)

        assert result.location_results == {}
        assert any("Unknown restaurant 'Unknown Outlet'" in n for n in result.global_notes)

    def test_untagged_fragments_route_to_fallback_location(self, monkeypatch):
        monkeypatch.setattr(
            smart_upload.file_detector,
            "detect_and_describe",
            lambda c, f: ("item_order_details", "item"),
        )
        monkeypatch.setattr(smart_upload.file_detector, "is_importable", lambda k: True)
        monkeypatch.setattr(smart_upload.file_detector, "is_skippable", lambda k: False)
        monkeypatch.setattr(
            smart_upload.pos_parser,
            "parse_item_order_details",
            lambda c, f: [
                {
                    "date": "2026-04-02",
                    "file_type": "item_order_details",
                    "net_total": 50.0,
                    "gross_total": 50.0,
                    "covers": 1,
                }
            ],
        )
        monkeypatch.setattr(
            smart_upload.database,
            "get_all_locations",
            lambda: [{"id": 11, "name": "Boteco - Indiqube"}],
        )
        monkeypatch.setattr(
            smart_upload.pos_parser,
            "group_fragments_by_date",
            lambda fragments: {"2026-04-02": fragments},
        )
        monkeypatch.setattr(
            smart_upload.pos_parser, "merge_upload_fragments", lambda frags: dict(frags[0])
        )
        monkeypatch.setattr(smart_upload.pos_parser, "validate_data", lambda data: (True, [], []))

        result = smart_upload.process_smart_upload([("item.xlsx", b"x")], location_id=77)

        assert 77 in result.location_results
        assert [d.date for d in result.location_results[77]] == ["2026-04-02"]

    def test_dynamic_report_beats_item_report_on_same_date(self, monkeypatch):
        monkeypatch.setattr(
            smart_upload.file_detector,
            "detect_and_describe",
            lambda c, f: ("dynamic_report", "d")
            if f.endswith(".csv")
            else ("item_order_details", "i"),
        )
        monkeypatch.setattr(smart_upload.file_detector, "is_importable", lambda k: True)
        monkeypatch.setattr(smart_upload.file_detector, "is_skippable", lambda k: False)
        monkeypatch.setattr(
            smart_upload.dynamic_report_parser,
            "parse_dynamic_report",
            lambda c, f: (
                [
                    {
                        "date": "2026-04-03",
                        "restaurant": "Boteco",
                        "file_type": "dynamic_report",
                        "net_total": 200.0,
                        "gross_total": 200.0,
                        "covers": 2,
                    }
                ],
                [],
            ),
        )
        monkeypatch.setattr(
            smart_upload.pos_parser,
            "parse_item_order_details",
            lambda c, f: [
                {
                    "date": "2026-04-03",
                    "file_type": "item_order_details",
                    "net_total": 10.0,
                    "gross_total": 10.0,
                    "covers": 1,
                }
            ],
        )
        monkeypatch.setattr(
            smart_upload.database,
            "get_all_locations",
            lambda: [{"id": 11, "name": "Boteco - Indiqube"}],
        )
        monkeypatch.setattr(
            smart_upload.pos_parser,
            "group_fragments_by_date",
            lambda fragments: {"2026-04-03": fragments},
        )
        monkeypatch.setattr(
            smart_upload.pos_parser, "merge_upload_fragments", lambda frags: dict(frags[0])
        )
        monkeypatch.setattr(smart_upload.pos_parser, "validate_data", lambda data: (True, [], []))

        result = smart_upload.process_smart_upload(
            [("dyn.csv", b"x"), ("item.xlsx", b"x")], location_id=11
        )

        day = result.location_results[11][0]
        assert day.source_kinds == ["dynamic_report"]
        assert day.merged["file_type"] == "dynamic_report"
