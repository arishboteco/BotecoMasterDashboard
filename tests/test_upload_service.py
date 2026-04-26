"""Tests for upload service preview/overlap/import helpers."""

from __future__ import annotations

from types import SimpleNamespace

from services.upload_service import ImportOptions, find_overlaps, import_upload, preview_upload
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
