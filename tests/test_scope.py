"""Tests for scope aggregation behavior used by Report tab PNG sections."""

import scope


def test_daily_report_bundle_uses_detailed_rows_for_services_and_categories(
    monkeypatch,
):
    monkeypatch.setattr(
        scope.database,
        "get_summaries_for_date_range_multi",
        lambda location_ids, start_date, end_date: [
            {
                "id": 101,
                "location_id": 1,
                "date": "2026-04-08",
                "net_total": 1000.0,
                "gross_total": 1100.0,
                "covers": 10,
                "complimentary": 80.0,
                "target": 10000.0,
            },
            {
                "id": 202,
                "location_id": 2,
                "date": "2026-04-08",
                "net_total": 1200.0,
                "gross_total": 1320.0,
                "covers": 12,
                "complimentary": 20.0,
                "target": 11000.0,
            },
        ],
    )
    monkeypatch.setattr(
        scope.database,
        "get_daily_summary",
        lambda location_id, date_str: {
            1: {
                "services": [{"service_type": "Lunch", "amount": 1000.0}],
                "categories": [{"category": "Food", "qty": 10, "amount": 1000.0}],
                "payment_methods": [
                    {"payment_method": "Zomato", "payment_key": "zomato", "amount": 500.0}
                ],
            },
            2: {
                "services": [{"service_type": "Lunch", "amount": 1200.0}],
                "categories": [{"category": "Food", "qty": 12, "amount": 1200.0}],
                "payment_methods": [
                    {"payment_method": "Razorpay", "payment_key": "razorpay", "amount": 250.0}
                ],
            },
        }[location_id],
    )
    monkeypatch.setattr(
        scope.database,
        "get_location_settings",
        lambda lid: {
            1: {"name": "Boteco - Indiqube", "target_monthly_sales": 300000},
            2: {"name": "Boteco - Bagmane", "target_monthly_sales": 300000},
        }[lid],
    )
    monkeypatch.setattr(
        scope, "enrich_summary_for_display", lambda s, *_args, **_kwargs: s
    )

    outlets, combined = scope.get_daily_report_bundle([1, 2], "2026-04-08")

    assert len(outlets) == 2
    assert combined is not None
    assert combined["complimentary"] == 100.0
    assert combined["services"] == [{"type": "Lunch", "amount": 2200.0}]
    assert combined["categories"] == [{"category": "Food", "qty": 22, "amount": 2200.0}]
    assert combined["payment_methods"] == [
        {"payment_method": "Zomato", "payment_key": "zomato", "amount": 500.0},
        {"payment_method": "Razorpay", "payment_key": "razorpay", "amount": 250.0},
    ]


def test_daily_report_bundle_accepts_total_key_for_category_amount(monkeypatch):
    monkeypatch.setattr(
        scope.database,
        "get_summaries_for_date_range_multi",
        lambda location_ids, start_date, end_date: [
            {
                "id": 101,
                "location_id": 1,
                "date": "2026-04-08",
                "net_total": 1000.0,
                "gross_total": 1100.0,
                "covers": 10,
                "complimentary": 0.0,
                "target": 10000.0,
            }
        ],
    )
    monkeypatch.setattr(
        scope.database,
        "get_daily_summary",
        lambda location_id, date_str: {
            "services": [{"service_type": "Lunch", "amount": 1000.0}],
            "categories": [{"category": "Food", "qty": 10, "total": 1000.0}],
        },
    )
    monkeypatch.setattr(
        scope.database,
        "get_location_settings",
        lambda lid: {"name": "Boteco - Indiqube", "target_monthly_sales": 300000},
    )
    monkeypatch.setattr(
        scope, "enrich_summary_for_display", lambda s, *_args, **_kwargs: s
    )

    outlets, combined = scope.get_daily_report_bundle([1], "2026-04-08")

    assert len(outlets) == 1
    assert combined is not None
    assert combined["categories"] == [{"category": "Food", "qty": 10, "amount": 1000.0}]


def test_daily_report_bundle_backfills_missing_daily_target(monkeypatch):
    monkeypatch.setattr(
        scope.database,
        "get_summaries_for_date_range_multi",
        lambda location_ids, start_date, end_date: [
            {
                "id": 101,
                "location_id": 1,
                "date": "2026-04-08",
                "net_total": 1000.0,
                "gross_total": 1100.0,
                "covers": 10,
                "target": 0.0,
            }
        ],
    )
    monkeypatch.setattr(
        scope.database,
        "get_daily_summary",
        lambda location_id, date_str: {
            "services": [{"service_type": "Lunch", "amount": 1000.0}],
            "categories": [{"category": "Food", "qty": 10, "amount": 1000.0}],
        },
    )
    monkeypatch.setattr(
        scope.database,
        "get_all_locations",
        lambda: [{"id": 1, "name": "Boteco - Indiqube", "target_monthly_sales": 300000}],
    )
    monkeypatch.setattr(
        scope.database,
        "get_location_settings",
        lambda _lid: {"id": 1, "name": "Boteco - Indiqube", "target_monthly_sales": 300000},
    )
    monkeypatch.setattr(scope.database, "get_recent_summaries", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(scope.utils, "compute_weekday_mix", lambda _rows: {"Tue": 1.0})
    monkeypatch.setattr(
        scope.utils,
        "compute_day_targets",
        lambda monthly, _mix, days_in_month=30: {"Tue": monthly / days_in_month},
    )
    monkeypatch.setattr(scope.utils, "get_target_for_date", lambda targets, _date: targets["Tue"])
    monkeypatch.setattr(scope, "enrich_summary_for_display", lambda s, *_args, **_kwargs: s)

    outlets, combined = scope.get_daily_report_bundle([1], "2026-04-08")

    assert len(outlets) == 1
    assert outlets[0][2]["target"] == 10000.0
    assert combined is not None
    assert combined["target"] == 10000.0


def test_synthetic_daily_summary_uses_actual_days_in_month(monkeypatch):
    monkeypatch.setattr(
        scope.database,
        "get_location_settings",
        lambda _lid: {"id": 1, "name": "Boteco - Indiqube", "target_monthly_sales": 6200000},
    )
    monkeypatch.setattr(scope.database, "get_recent_summaries", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(scope.utils, "compute_weekday_mix", lambda _rows: {"Sunday": 1.0})

    captured: dict = {}

    def _fake_compute_day_targets(monthly_target, weekday_mix, days_in_month=30):
        captured["days_in_month"] = days_in_month
        return {"Sunday": monthly_target / days_in_month}

    monkeypatch.setattr(scope.utils, "compute_day_targets", _fake_compute_day_targets)
    monkeypatch.setattr(
        scope.utils, "get_target_for_date", lambda targets, _date: targets["Sunday"]
    )

    out = scope._synthetic_daily_summary(1, "2026-05-03")

    assert captured["days_in_month"] == 31
    assert out["target"] == 200000.0
