"""Tests for centralized cache invalidation helpers."""

from services import cache_invalidation


class TestCacheInvalidation:
    def test_invalidate_reports_calls_report_clear(self, monkeypatch):
        called = {"count": 0}

        def _fake_clear_report_cache() -> None:
            called["count"] += 1

        monkeypatch.setattr(
            cache_invalidation.report_tab,
            "clear_report_cache",
            _fake_clear_report_cache,
        )

        cache_invalidation.invalidate_reports()

        assert called["count"] == 1

    def test_invalidate_analytics_calls_analytics_clear(self, monkeypatch):
        called = {"count": 0}

        def _fake_clear_analytics_cache() -> None:
            called["count"] += 1

        monkeypatch.setattr(
            cache_invalidation.analytics_tab,
            "clear_analytics_cache",
            _fake_clear_analytics_cache,
        )

        cache_invalidation.invalidate_analytics()

        assert called["count"] == 1

    def test_invalidate_location_reads_calls_location_clear(self, monkeypatch):
        called = {"location_ids": []}

        def _fake_clear_location_cache(location_id: int) -> None:
            called["location_ids"].append(location_id)

        monkeypatch.setattr(
            cache_invalidation,
            "clear_location_cache",
            _fake_clear_location_cache,
        )

        cache_invalidation.invalidate_location_reads(7)

        assert called["location_ids"] == [7]

    def test_invalidate_after_import_calls_all_groups(self, monkeypatch):
        called = {
            "location_ids": [],
            "analytics": 0,
            "reports": 0,
        }

        def _fake_invalidate_location_reads(location_id: int) -> None:
            called["location_ids"].append(location_id)

        def _fake_invalidate_analytics() -> None:
            called["analytics"] += 1

        def _fake_invalidate_reports() -> None:
            called["reports"] += 1

        monkeypatch.setattr(
            cache_invalidation,
            "invalidate_location_reads",
            _fake_invalidate_location_reads,
        )
        monkeypatch.setattr(
            cache_invalidation,
            "invalidate_analytics",
            _fake_invalidate_analytics,
        )
        monkeypatch.setattr(
            cache_invalidation,
            "invalidate_reports",
            _fake_invalidate_reports,
        )

        cache_invalidation.invalidate_after_import([2, 5])

        assert called["location_ids"] == [2, 5]
        assert called["analytics"] == 1
        assert called["reports"] == 1

    def test_invalidate_footfall_caches_clears_all_impacted_groups(self, monkeypatch):
        called = {
            "location_ids": [],
            "analytics": 0,
            "reports": 0,
        }

        def _fake_invalidate_location_reads(location_id: int) -> None:
            called["location_ids"].append(location_id)

        def _fake_invalidate_analytics() -> None:
            called["analytics"] += 1

        def _fake_invalidate_reports() -> None:
            called["reports"] += 1

        monkeypatch.setattr(
            cache_invalidation,
            "invalidate_location_reads",
            _fake_invalidate_location_reads,
        )
        monkeypatch.setattr(
            cache_invalidation,
            "invalidate_analytics",
            _fake_invalidate_analytics,
        )
        monkeypatch.setattr(
            cache_invalidation,
            "invalidate_reports",
            _fake_invalidate_reports,
        )
        cache_invalidation.report_service._REPORT_CACHE["report"] = object()
        cache_invalidation.report_service._FOOT_CACHE["foot"] = object()
        cache_invalidation.report_service._MTD_CACHE["mtd"] = object()

        cache_invalidation.invalidate_footfall_caches(7)

        assert called["location_ids"] == [7]
        assert called["analytics"] == 1
        assert called["reports"] == 1
        assert cache_invalidation.report_service._REPORT_CACHE == {}
        assert cache_invalidation.report_service._FOOT_CACHE == {}
        assert cache_invalidation.report_service._MTD_CACHE == {}
