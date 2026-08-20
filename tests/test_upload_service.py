"""Tests for upload service preview/overlap/import helpers."""

from __future__ import annotations

from types import SimpleNamespace

from services.upload_service import (
    ImportOptions,
    build_import_plan,
    find_duplicate_uploads,
    find_overlaps,
    import_upload,
    preview_upload,
    report_type_label,
    summarize_upload_history,
)
from uploads.models import DayResult, SmartUploadResult


class TestPreviewUpload:
    def test_calls_process_smart_upload(self, monkeypatch):
        files_payload = [("sample.csv", b"content")]
        expected = SmartUploadResult(files=[], days=[], global_notes=[], location_results={})

        def _fake_process(files, location_id):
            assert files == files_payload
            assert location_id == 17
            return expected

        monkeypatch.setattr(
            "services.upload_service.smart_upload.process_smart_upload", _fake_process
        )
        out = preview_upload(files_payload, 17)
        assert out is expected


class TestFindOverlaps:
    def test_returns_overlap_rows_for_valid_dates_only(self, monkeypatch):
        upload_result = SmartUploadResult(
            files=[],
            days=[],
            global_notes=[],
            location_results={
                10: [
                    DayResult(date="2026-04-01", merged={}, errors=[]),
                    DayResult(date="2026-04-02", merged={}, errors=["bad row"]),
                ],
                20: [
                    DayResult(date="2026-04-03", merged={}, errors=[]),
                ],
            },
        )
        calls = []

        def _fake_peek(location_id, dates):
            calls.append((location_id, dates))
            if location_id == 10:
                return {"2026-04-01": 123.0}
            return {"2026-04-03": 456.0}

        monkeypatch.setattr("services.upload_service.peek_existing_net_sales_batch", _fake_peek)
        rows = find_overlaps(upload_result)
        assert calls == [(10, ["2026-04-01"]), (20, ["2026-04-03"])]
        assert rows == [
            (10, "2026-04-01", 123.0),
            (20, "2026-04-03", 456.0),
        ]


class TestImportUpload:
    def test_uses_defaults_from_location_settings(self, monkeypatch):
        upload_result = SmartUploadResult(
            files=[], days=[], global_notes=[], location_results={1: []}
        )
        ctx = SimpleNamespace(location_id=99)
        captured = {}

        monkeypatch.setattr(
            "services.upload_service.database.get_location_settings",
            lambda _: {
                "target_monthly_sales": 1800000,
                "target_daily_sales": 60000,
                "seat_count": "120",
            },
        )
        monkeypatch.setattr(
            "services.upload_service.utils.compute_daily_target",
            lambda *_: 55555,
        )

        def _fake_save(*args, **kwargs):
            captured["args"] = args
            captured["kwargs"] = kwargs
            return (3, 1, ["ok"])

        monkeypatch.setattr(
            "services.upload_service.smart_upload.save_smart_upload_results", _fake_save
        )
        out = import_upload(upload_result, ctx, options=ImportOptions(uploaded_by="alice"))

        assert out == (3, 1, ["ok"])
        assert captured["args"] == (upload_result, 99, "alice")
        assert captured["kwargs"] == {
            "monthly_target": 1800000.0,
            "daily_target": 60000.0,
            "seat_count": 120,
        }

    def test_options_override_settings(self, monkeypatch):
        upload_result = SmartUploadResult(
            files=[], days=[], global_notes=[], location_results={1: []}
        )
        ctx = SimpleNamespace(location_id=99)
        captured = {}

        monkeypatch.setattr(
            "services.upload_service.database.get_location_settings",
            lambda _: {"target_monthly_sales": 100, "target_daily_sales": 10, "seat_count": 1},
        )
        monkeypatch.setattr(
            "services.upload_service.utils.compute_daily_target",
            lambda *_: 999,
        )

        def _fake_save(*args, **kwargs):
            captured["kwargs"] = kwargs
            return (1, 0, [])

        monkeypatch.setattr(
            "services.upload_service.smart_upload.save_smart_upload_results", _fake_save
        )
        import_upload(
            upload_result,
            ctx,
            options=ImportOptions(
                uploaded_by="bob",
                monthly_target=2500000,
                daily_target=80000,
                seat_count=88,
            ),
        )
        assert captured["kwargs"] == {
            "monthly_target": 2500000.0,
            "daily_target": 80000.0,
            "seat_count": 88,
        }


def _day(date: str, net_total: float, errors=None) -> DayResult:
    return DayResult(date=date, merged={"net_total": net_total}, errors=list(errors or []))


class TestBuildImportPlan:
    def test_all_new_days_no_replacements(self):
        upload_result = SimpleNamespace(
            location_results={1: [_day("2026-08-01", 1000.0), _day("2026-08-02", 2000.0)]},
            new_flow_meta={},
            category_by_loc={},
        )
        plan = build_import_plan(upload_result, [], {1: "Boteco - Indiqube"})

        assert plan.outlet_count == 1
        assert plan.total_days == 2
        assert plan.new_days == 2
        assert plan.replace_days == 0
        assert plan.net_total == 3000.0
        assert plan.has_replacements is False
        outlet = plan.outlets[0]
        assert outlet.location_name == "Boteco - Indiqube"
        assert outlet.date_min == "2026-08-01"
        assert outlet.date_max == "2026-08-02"

    def test_overlap_rows_become_replaced_days(self):
        upload_result = SimpleNamespace(
            location_results={1: [_day("2026-08-01", 1500.0), _day("2026-08-02", 2000.0)]},
            new_flow_meta={},
            category_by_loc={},
        )
        overlap_rows = [(1, "2026-08-01", 1000.0)]

        plan = build_import_plan(upload_result, overlap_rows, {1: "Boteco - Indiqube"})

        assert plan.replace_days == 1
        assert plan.new_days == 1
        assert plan.has_replacements is True
        assert len(plan.replaced) == 1
        replaced = plan.replaced[0]
        assert replaced.date == "2026-08-01"
        assert replaced.existing_net == 1000.0
        assert replaced.incoming_net == 1500.0
        assert replaced.delta == 500.0

    def test_days_with_errors_are_excluded(self):
        upload_result = SimpleNamespace(
            location_results={
                1: [_day("2026-08-01", 1000.0), _day("2026-08-02", 0.0, errors=["bad row"])]
            },
            new_flow_meta={},
            category_by_loc={},
        )
        plan = build_import_plan(upload_result, [], {1: "Boteco - Indiqube"})

        assert plan.total_days == 1
        assert plan.outlets[0].date_max == "2026-08-01"

    def test_flags_item_report_coverage_gap_beyond_growth_report(self):
        upload_result = SimpleNamespace(
            location_results={
                1: [_day("2026-08-01", 1000.0), _day("2026-08-19", 1200.0)]
            },
            new_flow_meta={
                "growth.xlsx": {
                    "detected_location_id": 1,
                    "file_type": "growth_report_day_wise",
                },
                "item.xlsx": {
                    "detected_location_id": 1,
                    "file_type": "item_order_details",
                },
            },
            category_by_loc={
                1: [{"date": "2026-04-16"}, {"date": "2026-08-19"}],
            },
        )
        plan = build_import_plan(upload_result, [], {1: "Boteco - Bagmane"})

        assert plan.has_coverage_warnings is True
        assert len(plan.coverage_warnings) == 1
        msg = plan.coverage_warnings[0]
        assert "Boteco - Bagmane" in msg
        assert "2026-04-16" in msg
        assert plan.outlets[0].coverage_gaps == plan.coverage_warnings

    def test_matching_coverage_has_no_warning(self):
        upload_result = SimpleNamespace(
            location_results={1: [_day("2026-08-01", 1000.0), _day("2026-08-19", 1200.0)]},
            new_flow_meta={
                "growth.xlsx": {
                    "detected_location_id": 1,
                    "file_type": "growth_report_day_wise",
                },
                "item.xlsx": {
                    "detected_location_id": 1,
                    "file_type": "item_order_details",
                },
            },
            category_by_loc={1: [{"date": "2026-08-01"}, {"date": "2026-08-19"}]},
        )
        plan = build_import_plan(upload_result, [], {1: "Boteco - Bagmane"})

        assert plan.has_coverage_warnings is False

    def test_unnamed_outlet_falls_back_to_generic_label(self):
        upload_result = SimpleNamespace(
            location_results={7: [_day("2026-08-01", 1000.0)]},
            new_flow_meta={},
            category_by_loc={},
        )
        plan = build_import_plan(upload_result, [], {})

        assert plan.outlets[0].location_name == "Outlet 7"


class TestSummarizeUploadHistory:
    def test_groups_day_rows_into_one_batch_per_file(self):
        rows = [
            {
                "date": "2026-08-01",
                "location_id": 1,
                "filename": "growth.xlsx",
                "file_hash": "abc123",
                "uploaded_by": "asha",
                "uploaded_at": "2026-08-19T10:00:00",
                "file_type": "growth_report_day_wise",
                "row_count": 19,
            },
            {
                "date": "2026-08-02",
                "location_id": 1,
                "filename": "growth.xlsx",
                "file_hash": "abc123",
                "uploaded_by": "asha",
                "uploaded_at": "2026-08-19T10:00:05",
                "file_type": "growth_report_day_wise",
                "row_count": 19,
            },
        ]
        batches = summarize_upload_history(rows, {1: "Boteco - Indiqube"})

        assert len(batches) == 1
        batch = batches[0]
        assert batch.days_saved == 2
        assert batch.filename == "growth.xlsx"
        assert batch.location_name == "Boteco - Indiqube"
        assert batch.report_label == "Growth Report"
        assert batch.covers_label == "2026-08-01 → 2026-08-02"

    def test_different_files_stay_separate_batches(self):
        rows = [
            {
                "date": "2026-08-01",
                "location_id": 1,
                "filename": "growth.xlsx",
                "file_hash": "hash1",
                "uploaded_by": "asha",
                "uploaded_at": "2026-08-19T10:00:00",
            },
            {
                "date": "2026-08-01",
                "location_id": 1,
                "filename": "item.xlsx",
                "file_hash": "hash2",
                "uploaded_by": "asha",
                "uploaded_at": "2026-08-19T10:05:00",
            },
        ]
        batches = summarize_upload_history(rows, {1: "Boteco - Indiqube"})

        assert len(batches) == 2

    def test_respects_limit_and_sorts_newest_first(self):
        rows = [
            {
                "date": "2026-08-01",
                "location_id": 1,
                "filename": f"file{i}.xlsx",
                "file_hash": f"hash{i}",
                "uploaded_by": "asha",
                "uploaded_at": f"2026-08-{i:02d}T10:00:00",
            }
            for i in range(1, 11)
        ]
        batches = summarize_upload_history(rows, {1: "Boteco - Indiqube"}, limit=3)

        assert len(batches) == 3
        assert batches[0].filename == "file10.xlsx"

    def test_falls_back_to_generic_outlet_name(self):
        rows = [
            {
                "date": "2026-08-01",
                "location_id": 5,
                "filename": "growth.xlsx",
                "file_hash": "abc",
                "uploaded_by": "asha",
                "uploaded_at": "2026-08-19T10:00:00",
            }
        ]
        batches = summarize_upload_history(rows, {})

        assert batches[0].location_name == "Outlet 5"


class TestFindDuplicateUploads:
    def test_matching_hash_flagged_as_duplicate(self):
        new_flow_meta = {"growth.xlsx": {"file_hash": "abc123"}}
        history_rows = [
            {
                "file_hash": "abc123",
                "uploaded_at": "2026-08-18T09:00:00",
                "uploaded_by": "asha",
            }
        ]
        duplicates = find_duplicate_uploads(new_flow_meta, history_rows)

        assert duplicates == [("growth.xlsx", "2026-08-18T09:00:00", "asha")]

    def test_no_hash_is_not_flagged(self):
        new_flow_meta = {"growth.xlsx": {}}
        history_rows = [{"file_hash": "abc123", "uploaded_at": "x", "uploaded_by": "asha"}]

        assert find_duplicate_uploads(new_flow_meta, history_rows) == []

    def test_no_matching_history_is_not_flagged(self):
        new_flow_meta = {"growth.xlsx": {"file_hash": "new_hash"}}
        history_rows = [{"file_hash": "old_hash", "uploaded_at": "x", "uploaded_by": "asha"}]

        assert find_duplicate_uploads(new_flow_meta, history_rows) == []

    def test_picks_most_recent_prior_match(self):
        new_flow_meta = {"growth.xlsx": {"file_hash": "abc123"}}
        history_rows = [
            {"file_hash": "abc123", "uploaded_at": "2026-08-01T09:00:00", "uploaded_by": "asha"},
            {"file_hash": "abc123", "uploaded_at": "2026-08-15T09:00:00", "uploaded_by": "bob"},
        ]
        duplicates = find_duplicate_uploads(new_flow_meta, history_rows)

        assert duplicates == [("growth.xlsx", "2026-08-15T09:00:00", "bob")]


class TestReportTypeLabel:
    def test_known_type(self):
        assert report_type_label("growth_report_day_wise") == "Growth Report"

    def test_unknown_type(self):
        assert report_type_label("something_else") == "—"
