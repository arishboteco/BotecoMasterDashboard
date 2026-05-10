"""Tests for report service data-loading helpers."""

from services import report_service


def setup_function() -> None:
    """Clear service-level caches before each test."""
    report_service._REPORT_CACHE.clear()
    report_service._MTD_CACHE.clear()
    report_service._FOOT_CACHE.clear()


def test_build_mtd_maps_caps_to_selected_date(monkeypatch):
    captured = {}

    def _fake_cat(location_ids, start_date, end_date):
        captured["cat"] = (location_ids, start_date, end_date)
        return [{"category": "Food", "amount": 2500.0}]

    def _fake_svc(location_ids, start_date, end_date):
        captured["svc"] = (location_ids, start_date, end_date)
        return [{"service_type": "Lunch", "amount": 1200.0}]

    monkeypatch.setattr(
        report_service.database,
        "get_category_sales_grouped_for_date_range",
        _fake_cat,
    )
    monkeypatch.setattr(
        report_service.database,
        "get_service_sales_for_date_range",
        _fake_svc,
    )

    mtd_cat, mtd_svc = report_service.build_mtd_maps([1, 2], 2026, 4, "2026-04-08")

    assert captured["cat"] == ([1, 2], "2026-04-01", "2026-04-08")
    assert captured["svc"] == ([1, 2], "2026-04-01", "2026-04-08")
    assert mtd_cat == {"Food": 2500.0}
    assert mtd_svc == {"Lunch": 1200.0}


def test_build_mtd_maps_accepts_total_keys(monkeypatch):
    monkeypatch.setattr(
        report_service.database,
        "get_category_sales_grouped_for_date_range",
        lambda *_args, **_kwargs: [{"category": "Food", "total": 500.0}],
    )
    monkeypatch.setattr(
        report_service.database,
        "get_service_sales_for_date_range",
        lambda *_args, **_kwargs: [{"type": "Dinner", "total": 700.0}],
    )

    mtd_cat, mtd_svc = report_service.build_mtd_maps([1], 2026, 4, "2026-04-08")

    assert mtd_cat == {"Food": 500.0}
    assert mtd_svc == {"Dinner": 700.0}


def test_load_report_bundle_cached_uses_cache(monkeypatch):
    calls = {"count": 0}

    def _fake_bundle(location_ids, date_str):
        calls["count"] += 1
        return [(1, "Outlet", {"net_total": 100.0})], {"net_total": 100.0}

    monkeypatch.setattr(report_service.scope, "get_daily_report_bundle", _fake_bundle)

    first = report_service.load_report_bundle_cached([1], "2026-04-08")
    second = report_service.load_report_bundle_cached([1], "2026-04-08")

    assert first == second
    assert calls["count"] == 1


def test_get_foot_rows_cached_selects_multi_and_caches(monkeypatch):
    calls = {"multi": 0}

    def _fake_multi(location_ids, year, month):
        calls["multi"] += 1
        return [{"date": "2026-04-01", "covers": 5}]

    monkeypatch.setattr(
        report_service.database,
        "get_summaries_for_month_multi",
        _fake_multi,
    )

    first = report_service.get_foot_rows_cached([1, 2], 2026, 4)
    second = report_service.get_foot_rows_cached([1, 2], 2026, 4)

    assert first == second
    assert calls["multi"] == 1


def test_clear_report_cache_clears_all_report_cache_stores():
    report_service._REPORT_CACHE[("report",)] = "stale-report"
    report_service._MTD_CACHE[("mtd",)] = "stale-mtd"
    report_service._FOOT_CACHE[("foot",)] = "stale-foot"

    report_service.clear_report_cache()

    assert report_service._REPORT_CACHE == {}
    assert report_service._MTD_CACHE == {}
    assert report_service._FOOT_CACHE == {}
