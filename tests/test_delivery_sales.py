"""Delivery channel regressions, including the November 2026 POS reconciliation."""

import json
from copy import deepcopy
from pathlib import Path

import pytest
from reportlab.platypus import Table

import sheet_reports
from services import report_service
from services.payment_mapping import delivery_sales_amount, is_delivery_payment_method


@pytest.mark.parametrize(
    "name,key,expected",
    [
        ("Swiggy", "swiggy", True),
        ("Other [SWIGGY]", "", True),
        ("Ownly", "ownly", True),
        ("Other [OWNLY]", "", True),
        ("Zomato Other", "zomato_other", True),
        ("Zomato Delivery", "zomato_delivery", True),
        ("Swiggy Delivery", "swiggy_delivery", True),
        ("Swiggy Dineout", "swiggy_dineout", False),
        ("Zomato District", "zomato_district", False),
        ("Zomato", "zomato", False),
        ("Eazydiner", "eazydiner", False),
        ("Razorpay", "razorpay", False),
    ],
)
def test_delivery_mapping_excludes_dine_in_providers(name, key, expected):
    assert is_delivery_payment_method(name, key) is expected


def _payments(zomato=0.0, swiggy=0.0, ownly=0.0):
    return [
        {"payment_method": "Zomato Delivery", "amount": zomato},
        {"payment_method": "Swiggy", "amount": swiggy},
        {"payment_method": "Ownly", "amount": ownly},
        {"payment_method": "Swiggy Dineout", "amount": 10000.0},
        {"payment_method": "Zomato District", "amount": 20000.0},
    ]


@pytest.mark.parametrize("stored", [3282.0, 20020.0])
def test_delivery_reconciles_partial_and_complete_summaries_without_adding_sources(stored):
    # Bagmane 2026-11-01: POS gross 160,562 minus dine-in 140,542 = 20,020.
    summary = {"delivery_sales": stored, "payment_methods": _payments(3282.0, 16738.0)}
    before = deepcopy(summary)
    assert delivery_sales_amount(summary) == 20020.0
    assert summary == before


def test_delivery_preserves_larger_order_type_total_and_service_fallback():
    assert (
        delivery_sales_amount(
            {"delivery_sales": 25000.0, "payment_methods": _payments(3282.0, 16738.0)}
        )
        == 25000.0
    )
    assert delivery_sales_amount({"services": [{"type": "Delivery", "amount": 500.0}]}) == 500.0
    assert delivery_sales_amount({}) == 0.0


def test_ambiguous_historical_provider_does_not_reclassify_pos_dine_in_sales():
    # Indiqube 2026-10-06: the POS attributes ALL gross sales to dine-in.
    assert (
        delivery_sales_amount(
            {
                "gross_total": 116296.0,
                "dine_in_sales": 116296.0,
                "delivery_sales": 0.0,
                "payment_methods": _payments(swiggy=5348.0),
            }
        )
        == 0.0
    )
    # Bagmane 2026-08-26 has conflicting old summary/tender data: preserve it.
    assert (
        delivery_sales_amount(
            {
                "gross_total": 60115.0,
                "dine_in_sales": 59144.0,
                "delivery_sales": 4453.0,
                "payment_methods": [
                    {"payment_method": "Swiggy Delivery", "amount": 4453.0},
                    {"payment_method": "Ownly", "amount": 971.0},
                ],
            }
        )
        == 4453.0
    )


def test_mtd_resolves_each_outlet_day_and_uses_selected_range(monkeypatch):
    calls = []
    summaries = [
        {"location_id": 2, "date": "2026-11-01", "delivery_sales": 3282.0},
        {"location_id": 2, "date": "2026-11-02", "delivery_sales": 10000.0},
        {"location_id": 1, "date": "2026-11-01", "delivery_sales": 0.0},
    ]
    payments = [{"location_id": 2, "date": "2026-11-01", **p} for p in _payments(3282.0, 16738.0)]
    # A payment-only day without a summary must still be counted once.
    payments.append(
        {"location_id": 2, "date": "2026-11-03", "payment_method": "Ownly", "amount": 788.0}
    )

    def scoped(rows):
        def fetch(ids, start, end):
            calls.append((ids, start, end))
            return rows

        return fetch

    monkeypatch.setattr(
        report_service.database, "get_summaries_for_date_range_multi", scoped(summaries)
    )
    monkeypatch.setattr(
        report_service.database, "get_payment_method_sales_for_date_range_multi", scoped(payments)
    )
    monkeypatch.setattr(
        report_service.database,
        "get_category_sales_grouped_for_date_range",
        lambda *_: [{"category": "Food", "amount": 50000.0}],
    )
    monkeypatch.setattr(
        report_service.database,
        "get_service_sales_for_date_range",
        lambda *_: [{"type": "Lunch", "amount": 50000.0}],
    )
    before = deepcopy(summaries)
    cats, services = report_service.build_mtd_maps([1, 2], 2026, 11, "2026-11-03")
    assert calls == [([1, 2], "2026-11-01", "2026-11-03")] * 2
    assert cats == {"Food": 50000.0}
    assert services == {"Lunch": 50000.0, "Delivery": 30808.0}
    assert summaries == before


def test_category_combined_delivery_equals_outlet_columns_and_does_not_inflate_totals():
    outlets = [
        (
            "Indiqube",
            {"delivery_sales": 500.0, "categories": [{"category": "Food", "amount": 1000.0}]},
        ),
        (
            "Bagmane",
            {
                "delivery_sales": 3282.0,
                "payment_methods": _payments(3282.0, 16738.0),
                "categories": [{"category": "Food", "amount": 30000.0}],
            },
        ),
    ]
    combined = {
        "delivery_sales": 3782.0,
        "payment_methods": _payments(3282.0, 16738.0),
        "categories": [{"category": "Food", "amount": 31000.0}],
    }
    elements = sheet_reports._build_category(
        combined,
        "All outlets",
        {"Food": 50000.0},
        "1 Nov 2026",
        per_outlet=outlets,
        mtd_service={"Delivery": 20520.0},
    )
    table = next(element for element in elements if isinstance(element, Table))
    rows = {row[0]: row[1:] for row in table._cellvalues if row}
    assert rows["Delivery"] == ["₹500", "₹20,020", "₹20,520", "₹20,520"]
    assert rows["Category Total"] == ["₹1,000", "₹30,000", "₹31,000", "₹50,000"]


@pytest.mark.parametrize("ids,expected", [([1], 0.0), ([2], 244011.0), ([1, 2], 244011.0)])
def test_november_pos_snapshot_reconciles_daily_and_mtd(monkeypatch, ids, expected):
    snapshot = json.loads(
        (Path(__file__).parent / "fixtures" / "delivery_november_2026.json").read_text()
    )
    summaries = [dict(zip(snapshot["columns"], row, strict=True)) for row in snapshot["rows"]]
    summaries = [row for row in summaries if row["location_id"] in ids]
    payment_rows = []
    daily_total = 0.0
    for row in summaries:
        payments = _payments(row["zomato_delivery"], row["swiggy"], row["ownly"])
        # _payments also includes deliberately excluded dine-in providers.
        delivery = delivery_sales_amount({**row, "payment_methods": payments})
        assert delivery == (
            row["gross_total"] - row["dine_in_sales"] - row["pickup_sales"] - row["menu_qr_sales"]
        )
        daily_total += delivery
        payment_rows.extend(
            {"location_id": row["location_id"], "date": row["date"], **p} for p in payments
        )
    monkeypatch.setattr(
        report_service.database, "get_summaries_for_date_range_multi", lambda *_: summaries
    )
    monkeypatch.setattr(
        report_service.database,
        "get_payment_method_sales_for_date_range_multi",
        lambda *_: payment_rows,
    )
    monkeypatch.setattr(
        report_service.database, "get_category_sales_grouped_for_date_range", lambda *_: []
    )
    monkeypatch.setattr(report_service.database, "get_service_sales_for_date_range", lambda *_: [])
    _, services = report_service.build_mtd_maps(ids, 2026, 11, "2026-11-20")
    assert daily_total == expected
    assert services.get("Delivery", 0.0) == expected
