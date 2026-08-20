"""Tests for smart_upload save metadata behavior."""

import smart_upload
from smart_upload import DayResult, SmartUploadResult


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


class TestSaveSmartUploadResults:
    def test_supabase_item_only_split_updates_existing_growth_daily_row(self, monkeypatch):
        captured_daily_rows = []
        captured_payment_rows = []
        deleted_payment_pairs = []

        monkeypatch.setattr(smart_upload.database, "use_supabase", lambda: True)
        monkeypatch.setattr(smart_upload.database, "get_supabase_client", lambda: object())
        monkeypatch.setattr(
            smart_upload.database,
            "get_daily_summary",
            lambda loc_id, date: {
                "date": date,
                "gross_total": 1000.0,
                "net_total": 900.0,
                "upi_sales": 805.0,
                "gpay_sales": 0.0,
                "payment_methods": [
                    {"payment_method": "Zomato", "payment_key": "zomato", "amount": 100.0},
                    {"payment_method": "UPI", "payment_key": "upi", "amount": 805.0},
                ],
                "source_report": "growth_report_day_wise",
            },
        )

        import database_writes

        monkeypatch.setattr(
            database_writes,
            "upsert_daily_summaries_supabase_batch",
            lambda client, rows: captured_daily_rows.extend(rows),
        )
        monkeypatch.setattr(
            database_writes,
            "delete_category_summary_batch",
            lambda client, dates_locs: None,
        )
        monkeypatch.setattr(
            database_writes,
            "save_category_summary_batch",
            lambda client, records: None,
        )
        monkeypatch.setattr(
            database_writes,
            "delete_payment_method_sales_batch",
            lambda client, dates_locs: deleted_payment_pairs.extend(sorted(dates_locs)),
        )
        monkeypatch.setattr(
            database_writes,
            "save_payment_method_sales_batch",
            lambda client, records: captured_payment_rows.extend(records),
        )
        monkeypatch.setattr(
            database_writes,
            "save_upload_records_batch",
            lambda rows: None,
        )
        monkeypatch.setattr(
            database_writes,
            "delete_bill_items_by_dates_locs",
            lambda client, dates_locs: None,
        )
        monkeypatch.setattr(
            database_writes,
            "save_bill_items",
            lambda client, records: None,
        )

        result = SmartUploadResult(
            files=[],
            days=[],
            location_results={
                2: [
                    DayResult(
                        date="2026-05-05",
                        merged={
                            "date": "2026-05-05",
                            "categories_new": [],
                        },
                        source_kinds=["item_order_details"],
                    )
                ]
            },
        )
        result.item_payment_split_by_loc = {  # type: ignore[attr-defined]
            2: {
                "2026-05-05": [
                    {"payment_method": "GPay", "payment_key": "gpay", "amount": 305.0},
                    {"payment_method": "Razorpay", "payment_key": "razorpay", "amount": 500.0},
                ]
            }
        }
        result.category_by_loc = {2: []}  # type: ignore[attr-defined]
        result.item_service_by_loc = {}  # type: ignore[attr-defined]
        result.new_flow_meta = {}  # type: ignore[attr-defined]

        saved, skipped, _messages = smart_upload.save_smart_upload_results(
            result,
            location_id=2,
            uploaded_by="tester",
        )

        assert saved == 1
        assert skipped == 0
        assert captured_daily_rows == [
            {
                "location_id": 2,
                "date": "2026-05-05",
                "gross_total": 1000.0,
                "net_total": 900.0,
                "covers": 0,
                "discount": 0.0,
                "cgst": 0.0,
                "sgst": 0.0,
                "service_charge": 0.0,
                "gst_on_service_charge": 0.0,
                "cancelled_amount": 0.0,
                "complementary_amount": 0.0,
                "order_count": 0,
                "cash_sales": 0.0,
                "card_sales": 0.0,
                "gpay_sales": 305.0,
                "zomato_sales": 0.0,
                "my_amount": 0.0,
                "total_tax": 0.0,
                "round_off": 0.0,
                "expenses": 0.0,
                "due_payment_sales": 0.0,
                "wallet_sales": 0.0,
                "upi_sales": 0.0,
                "bank_transfer_sales": 0.0,
                "boh_sales": 0.0,
                "delivery_sales": 0.0,
                "pickup_sales": 0.0,
                "dine_in_sales": 0.0,
                "menu_qr_sales": 0.0,
                "source_report": "growth_report_day_wise",
            }
        ]
        assert deleted_payment_pairs == [("2026-05-05", 2)]
        assert captured_payment_rows == [
            {
                "location_id": 2,
                "date": "2026-05-05",
                "payment_method": "Zomato",
                "payment_key": "zomato",
                "amount": 100.0,
                "source_report": "item_report_payment_split",
            },
            {
                "location_id": 2,
                "date": "2026-05-05",
                "payment_method": "Razorpay",
                "payment_key": "razorpay",
                "amount": 500.0,
                "source_report": "item_report_payment_split",
            },
        ]

    def test_supabase_saves_item_report_service_sales_using_timestamp_buckets(self, monkeypatch):
        captured_bill_items = []

        monkeypatch.setattr(smart_upload.database, "use_supabase", lambda: True)
        monkeypatch.setattr(smart_upload.database, "get_supabase_client", lambda: object())

        import database_writes

        monkeypatch.setattr(
            database_writes,
            "upsert_daily_summaries_supabase_batch",
            lambda client, rows: None,
        )
        monkeypatch.setattr(
            database_writes,
            "delete_category_summary_batch",
            lambda client, dates_locs: None,
        )
        monkeypatch.setattr(
            database_writes,
            "save_category_summary_batch",
            lambda client, records: None,
        )
        monkeypatch.setattr(
            database_writes,
            "save_upload_records_batch",
            lambda rows: None,
        )
        monkeypatch.setattr(
            database_writes,
            "delete_bill_items_by_dates_locs",
            lambda client, dates_locs: None,
        )
        monkeypatch.setattr(
            database_writes,
            "save_bill_items",
            lambda client, records: captured_bill_items.extend(records),
        )

        result = SmartUploadResult(
            files=[],
            days=[],
            location_results={
                2: [
                    DayResult(
                        date="2026-05-02",
                        merged={
                            "date": "2026-05-02",
                            "net_total": 1000.0,
                            "services": [
                                {"type": "Lunch", "amount": 400.0},
                                {"type": "Dinner", "amount": 600.0},
                            ],
                        },
                        source_kinds=["item_order_details"],
                    )
                ]
            },
        )

        saved, skipped, _messages = smart_upload.save_smart_upload_results(
            result,
            location_id=2,
            uploaded_by="tester",
        )

        assert saved == 1
        assert skipped == 0
        assert len(captured_bill_items) == 2
        assert {r["created_date_time"] for r in captured_bill_items} == {
            "2026-05-02 13:00:00",
            "2026-05-02 20:00:00",
        }
        assert {r["net_amount"] for r in captured_bill_items} == {400.0, 600.0}

    def test_supabase_saves_new_flow_item_report_timestamp_service_sales(self, monkeypatch):
        captured_bill_items = []

        monkeypatch.setattr(smart_upload.database, "use_supabase", lambda: True)
        monkeypatch.setattr(smart_upload.database, "get_supabase_client", lambda: object())

        import database_writes

        monkeypatch.setattr(
            database_writes,
            "upsert_daily_summaries_supabase_batch",
            lambda client, rows: None,
        )
        monkeypatch.setattr(
            database_writes,
            "delete_category_summary_batch",
            lambda client, dates_locs: None,
        )
        monkeypatch.setattr(
            database_writes,
            "save_category_summary_batch",
            lambda client, records: None,
        )
        monkeypatch.setattr(
            database_writes,
            "save_upload_records_batch",
            lambda rows: None,
        )
        monkeypatch.setattr(
            database_writes,
            "delete_bill_items_by_dates_locs",
            lambda client, dates_locs: None,
        )
        monkeypatch.setattr(
            database_writes,
            "save_bill_items",
            lambda client, records: captured_bill_items.extend(records),
        )

        result = SmartUploadResult(
            files=[],
            days=[],
            location_results={
                2: [
                    DayResult(
                        date="2026-05-03",
                        merged={
                            "date": "2026-05-03",
                            "net_total": 1000.0,
                            "source_report": "growth_report_day_wise",
                        },
                        source_kinds=["growth_report_day_wise"],
                    )
                ]
            },
        )
        result.item_service_by_loc = {  # type: ignore[attr-defined]
            2: {
                "2026-05-03": [
                    {"type": "Lunch", "amount": 450.0},
                    {"type": "Dinner", "amount": 550.0},
                ]
            }
        }
        result.category_by_loc = {2: []}  # type: ignore[attr-defined]
        result.new_flow_meta = {}  # type: ignore[attr-defined]

        saved, skipped, _messages = smart_upload.save_smart_upload_results(
            result,
            location_id=2,
            uploaded_by="tester",
        )

        assert saved == 1
        assert skipped == 0
        assert len(captured_bill_items) == 2
        assert {r["created_date_time"] for r in captured_bill_items} == {
            "2026-05-03 13:00:00",
            "2026-05-03 20:00:00",
        }
        assert {r["net_amount"] for r in captured_bill_items} == {450.0, 550.0}


class TestCheckCompletenessDateCoverage:
    """_check_completeness must compare date coverage, not just presence.

    Regression: an Item Report spanning more days than its Growth Report
    (or vice versa) used to pass silently — only whether each report type
    existed at all was checked. This is the exact shape of a real
    production incident where months of category data had no matching
    service split and nothing warned about it.
    """

    def _meta(self, loc_id, name):
        return {f"{name}.xlsx": {"detected_location_id": loc_id, "detected_location_name": name}}

    def test_flags_item_report_covering_more_days_than_growth_report(self):
        daily_by_loc = {2: [{"date": "2026-08-01"}, {"date": "2026-08-19"}]}
        cat_by_loc = {
            2: [
                {"date": "2026-04-16"},
                {"date": "2026-06-01"},
                {"date": "2026-08-01"},
                {"date": "2026-08-19"},
            ]
        }
        notes: list[str] = []

        smart_upload._check_completeness(
            daily_by_loc, cat_by_loc, notes, self._meta(2, "Boteco - Bagmane")
        )

        assert len(notes) == 1
        assert "Boteco - Bagmane" in notes[0]
        assert "2026-04-16" in notes[0]
        assert "2 day(s)" in notes[0]

    def test_flags_growth_report_covering_more_days_than_item_report(self):
        daily_by_loc = {1: [{"date": "2026-02-06"}, {"date": "2026-08-19"}]}
        cat_by_loc = {1: [{"date": "2026-08-19"}]}
        notes: list[str] = []

        smart_upload._check_completeness(
            daily_by_loc, cat_by_loc, notes, self._meta(1, "Boteco - Indiqube")
        )

        assert len(notes) == 1
        assert "Boteco - Indiqube" in notes[0]
        assert "1 day(s)" in notes[0]

    def test_matching_coverage_produces_no_note(self):
        daily_by_loc = {1: [{"date": "2026-08-01"}, {"date": "2026-08-02"}]}
        cat_by_loc = {1: [{"date": "2026-08-01"}, {"date": "2026-08-02"}]}
        notes: list[str] = []

        smart_upload._check_completeness(
            daily_by_loc, cat_by_loc, notes, self._meta(1, "Boteco - Indiqube")
        )

        assert notes == []

    def test_missing_item_report_entirely_still_uses_outlet_name(self):
        daily_by_loc = {2: [{"date": "2026-08-01"}]}
        cat_by_loc: dict = {}
        notes: list[str] = []

        smart_upload._check_completeness(
            daily_by_loc, cat_by_loc, notes, self._meta(2, "Boteco - Bagmane")
        )

        assert len(notes) == 1
        assert "Boteco - Bagmane" in notes[0]
        assert "Outlet 2" not in notes[0]

    def test_falls_back_to_generic_name_when_meta_missing(self):
        daily_by_loc = {5: [{"date": "2026-08-01"}]}
        cat_by_loc: dict = {}
        notes: list[str] = []

        smart_upload._check_completeness(daily_by_loc, cat_by_loc, notes, {})

        assert "Outlet 5" in notes[0]


class TestFindSourceFilenameScopedByLocation:
    """A multi-outlet upload must not attribute one outlet's filename to another's."""

    def _result_with_two_growth_files(self):
        from uploads.models import FileResult

        return SmartUploadResult(
            files=[
                FileResult(
                    filename="indiqube_growth.xlsx",
                    kind="growth_report_day_wise",
                    kind_label="Growth Report Day Wise",
                    importable=True,
                ),
                FileResult(
                    filename="bagmane_growth.xlsx",
                    kind="growth_report_day_wise",
                    kind_label="Growth Report Day Wise",
                    importable=True,
                ),
            ],
            days=[],
            location_results={},
        )

    def test_returns_the_filename_matching_the_requested_outlet(self):
        result = self._result_with_two_growth_files()
        new_flow_meta = {
            "indiqube_growth.xlsx": {"detected_location_id": 1},
            "bagmane_growth.xlsx": {"detected_location_id": 2},
        }

        assert (
            smart_upload._find_source_filename(
                result, "growth_report_day_wise", new_flow_meta, 1
            )
            == "indiqube_growth.xlsx"
        )
        assert (
            smart_upload._find_source_filename(
                result, "growth_report_day_wise", new_flow_meta, 2
            )
            == "bagmane_growth.xlsx"
        )

    def test_without_loc_filter_returns_first_match(self):
        # Backward-compatible behavior when loc_id/new_flow_meta are omitted.
        result = self._result_with_two_growth_files()

        assert (
            smart_upload._find_source_filename(result, "growth_report_day_wise")
            == "indiqube_growth.xlsx"
        )


class TestNewFlowMetaFileType:
    """meta['file_type'] must be set so downstream UI (e.g. the comp-report
    completeness badge) can key off it — previously no parser ever set it.
    """

    def test_growth_report_meta_has_file_type(self, monkeypatch):
        def _fake_parse(content, fname, loc_id):
            return [{"date": "2026-08-01", "net_total": 100.0}], [], {}

        def _fake_detect(content, fname, fallback):
            return 1, "Indiqube", "exact"

        monkeypatch.setattr(smart_upload, "parse_growth_report_day_wise", _fake_parse)
        monkeypatch.setattr(smart_upload, "_detect_location_for_file", _fake_detect)

        daily_by_loc, _cat, meta, _svc, _pay = smart_upload._process_new_flow_files(
            growth_files=[("growth.xlsx", b"data")],
            item_files=[],
            fallback_location_id=1,
            filename_to_fr={},
            global_notes=[],
        )

        assert meta["growth.xlsx"]["file_type"] == "growth_report_day_wise"
        assert daily_by_loc[1]


class TestBuildImportSummary:
    def test_none_merged_returns_none(self):
        assert smart_upload._build_import_summary(None, None) is None

    def test_compact_json_with_net_total_and_covers(self):
        import json

        summary = smart_upload._build_import_summary(
            {"net_total": 12345.678, "covers": 40}, None
        )

        assert json.loads(summary) == {"net_total": 12345.68, "covers": 40}

    def test_includes_warning_count_when_present(self):
        import json

        summary = smart_upload._build_import_summary(
            {"net_total": 1000.0, "covers": 10}, ["bad thing", "another bad thing"]
        )

        assert json.loads(summary)["warnings"] == 2

    def test_omits_warnings_key_when_empty(self):
        import json

        summary = smart_upload._build_import_summary({"net_total": 1000.0, "covers": 10}, [])

        assert "warnings" not in json.loads(summary)


class TestBuildUploadHistoryRow:
    def test_includes_import_summary_when_merged_given(self):
        row = smart_upload._build_upload_history_row(
            loc_id=1,
            date_str="2026-08-01",
            filename="growth.xlsx",
            file_type="growth_report_day_wise",
            uploaded_by="asha",
            fmeta={},
            merged={"net_total": 5000.0, "covers": 20},
            warnings=["a warning"],
        )

        assert row["import_summary"] is not None
        import json

        assert json.loads(row["import_summary"]) == {
            "net_total": 5000.0,
            "covers": 20,
            "warnings": 1,
        }

    def test_import_summary_none_without_merged(self):
        row = smart_upload._build_upload_history_row(
            loc_id=1,
            date_str="2026-08-01",
            filename="growth.xlsx",
            file_type="growth_report_day_wise",
            uploaded_by="asha",
            fmeta={},
        )

        assert row["import_summary"] is None
