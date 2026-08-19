"""Tests for services.data_quality — the Upload page data-health audit."""

from __future__ import annotations

from services import data_quality


def _patch_summaries(monkeypatch, rows):
    monkeypatch.setattr(
        "database.get_summaries_for_date_range_multi",
        lambda location_ids, start, end: rows,
    )


def _patch_categories(monkeypatch, rows):
    monkeypatch.setattr(
        "database_reads.get_category_totals_for_date_range",
        lambda location_ids, start, end: rows,
    )


class TestCategoryMissingDays:
    def test_flags_day_with_net_sales_but_no_category_rows(self, monkeypatch):
        _patch_summaries(
            monkeypatch,
            [{"location_id": 1, "date": "2026-04-05", "net_total": 50000}],
        )
        _patch_categories(monkeypatch, [])

        out = data_quality.audit_month_data_quality(
            [1], {1: "Bagmane"}, year=2026, month=4, as_of_date="2026-04-05"
        )

        assert len(out) == 1
        assert out[0].category_missing_days == ["2026-04-05"]
        assert out[0].category_mismatches == []
        assert out[0].has_issues is True

    def test_zero_net_sales_day_is_not_flagged(self, monkeypatch):
        _patch_summaries(
            monkeypatch,
            [{"location_id": 1, "date": "2026-04-05", "net_total": 0}],
        )
        _patch_categories(monkeypatch, [])

        out = data_quality.audit_month_data_quality(
            [1], {1: "Bagmane"}, year=2026, month=4, as_of_date="2026-04-05"
        )

        assert out[0].category_missing_days == []


class TestCategoryMismatch:
    def test_flags_material_mismatch(self, monkeypatch):
        _patch_summaries(
            monkeypatch,
            [{"location_id": 1, "date": "2026-04-05", "net_total": 100000}],
        )
        _patch_categories(
            monkeypatch,
            [
                {"location_id": 1, "date": "2026-04-05", "net_amount": 60000},
                {"location_id": 1, "date": "2026-04-05", "net_amount": 20000},
            ],
        )

        out = data_quality.audit_month_data_quality(
            [1], {1: "Bagmane"}, year=2026, month=4, as_of_date="2026-04-05"
        )

        assert len(out[0].category_mismatches) == 1
        mismatch = out[0].category_mismatches[0]
        assert mismatch.date == "2026-04-05"
        assert mismatch.net_total == 100000
        assert mismatch.category_total == 80000
        assert mismatch.diff == 20000

    def test_small_rounding_gap_is_not_flagged(self, monkeypatch):
        _patch_summaries(
            monkeypatch,
            [{"location_id": 1, "date": "2026-04-01", "net_total": 100000}],
        )
        _patch_categories(
            monkeypatch,
            [{"location_id": 1, "date": "2026-04-01", "net_amount": 99990}],
        )

        out = data_quality.audit_month_data_quality(
            [1], {1: "Bagmane"}, year=2026, month=4, as_of_date="2026-04-01"
        )

        assert out[0].category_mismatches == []
        assert out[0].category_missing_days == []
        assert out[0].has_issues is False


class TestMissingCalendarDays:
    def test_flags_gap_with_no_upload_at_all(self, monkeypatch):
        _patch_summaries(
            monkeypatch,
            [
                {"location_id": 1, "date": "2026-04-01", "net_total": 40000},
                {"location_id": 1, "date": "2026-04-03", "net_total": 45000},
            ],
        )
        _patch_categories(monkeypatch, [])

        out = data_quality.audit_month_data_quality(
            [1], {1: "Bagmane"}, year=2026, month=4, as_of_date="2026-04-03"
        )

        assert out[0].missing_days == ["2026-04-02"]

    def test_does_not_flag_today_as_missing(self, monkeypatch):
        _patch_summaries(monkeypatch, [])
        _patch_categories(monkeypatch, [])

        out = data_quality.audit_month_data_quality(
            [1], {1: "Bagmane"}, year=2026, month=4, as_of_date="2026-04-05"
        )

        assert "2026-04-05" not in out[0].missing_days
        assert out[0].missing_days == ["2026-04-01", "2026-04-02", "2026-04-03", "2026-04-04"]


class TestMultiLocation:
    def test_each_location_audited_independently(self, monkeypatch):
        _patch_summaries(
            monkeypatch,
            [
                {"location_id": 1, "date": "2026-04-01", "net_total": 40000},
                {"location_id": 2, "date": "2026-04-01", "net_total": 30000},
            ],
        )
        _patch_categories(
            monkeypatch,
            [{"location_id": 1, "date": "2026-04-01", "net_amount": 40000}],
        )

        out = data_quality.audit_month_data_quality(
            [1, 2], {1: "Bagmane", 2: "Indiqube"}, year=2026, month=4, as_of_date="2026-04-01"
        )

        by_loc = {r.location_id: r for r in out}
        assert by_loc[1].has_issues is False
        assert by_loc[2].category_missing_days == ["2026-04-01"]

    def test_no_locations_returns_empty(self):
        assert data_quality.audit_month_data_quality([], {}, year=2026, month=4) == []
