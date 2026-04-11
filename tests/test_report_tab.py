"""Tests for report tab data preparation helpers."""

from tabs import report_tab


def test_build_mtd_maps_caps_to_selected_date(monkeypatch):
    captured = {}

    def _fake_cat(location_ids, start_date, end_date):
        captured["cat"] = (location_ids, start_date, end_date)
        return [{"category": "Food", "amount": 2500.0}]

    def _fake_svc(location_ids, start_date, end_date):
        captured["svc"] = (location_ids, start_date, end_date)
        return [{"service_type": "Lunch", "amount": 1200.0}]

    monkeypatch.setattr(
        report_tab.database, "get_category_sales_for_date_range", _fake_cat
    )
    monkeypatch.setattr(
        report_tab.database, "get_service_sales_for_date_range", _fake_svc
    )

    mtd_cat, mtd_svc = report_tab._build_mtd_maps([1, 2], 2026, 4, "2026-04-08")

    assert captured["cat"] == ([1, 2], "2026-04-01", "2026-04-08")
    assert captured["svc"] == ([1, 2], "2026-04-01", "2026-04-08")
    assert mtd_cat == {"Food": 2500.0}
    assert mtd_svc == {"Lunch": 1200.0}


def test_build_mtd_maps_accepts_total_keys(monkeypatch):
    monkeypatch.setattr(
        report_tab.database,
        "get_category_sales_for_date_range",
        lambda *_args, **_kwargs: [{"category": "Food", "total": 500.0}],
    )
    monkeypatch.setattr(
        report_tab.database,
        "get_service_sales_for_date_range",
        lambda *_args, **_kwargs: [{"type": "Dinner", "total": 700.0}],
    )

    mtd_cat, mtd_svc = report_tab._build_mtd_maps([1], 2026, 4, "2026-04-08")

    assert mtd_cat == {"Food": 500.0}
    assert mtd_svc == {"Dinner": 700.0}
