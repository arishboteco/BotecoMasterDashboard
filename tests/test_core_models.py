"""Tests for core canonical dataclasses."""

from core.models import CategorySale, DailySummary, ServiceSale


def test_daily_summary_from_dict_and_to_dict_round_trip_preserves_extra_fields():
    payload = {
        "location_id": 2,
        "date": "2026-04-20",
        "covers": 145,
        "net_total": 50234.5,
        "categories": [{"category_name": "Food", "amount": 41000}],
        "services": [{"service_type": "Lunch", "amount": 23000}],
        "top_items": [{"item_name": "Butter Chicken", "qty": 14}],
        "custom_metric": 9.2,
    }

    summary = DailySummary.from_dict(payload)

    assert summary.location_id == 2
    assert summary.net_total == 50234.5
    assert summary.categories[0]["category_name"] == "Food"
    assert summary.extra == {"custom_metric": 9.2}

    serialized = summary.to_dict()
    assert serialized["custom_metric"] == 9.2
    assert serialized["covers"] == 145
    assert serialized["services"][0]["service_type"] == "Lunch"


def test_category_sale_from_dict_supports_legacy_aliases():
    category = CategorySale.from_dict(
        {
            "category": "Beverages",
            "total": 9876.0,
            "location_id": 1,
            "date": "2026-04-10",
            "source": "legacy_view",
        }
    )

    assert category.category_name == "Beverages"
    assert category.amount == 9876.0
    assert category.extra == {"source": "legacy_view"}


def test_service_sale_from_dict_supports_type_alias():
    service = ServiceSale.from_dict(
        {
            "type": "Dinner",
            "total": 12345.0,
            "location_id": 3,
            "date": "2026-04-11",
            "note": "approx",
        }
    )

    assert service.service_type == "Dinner"
    assert service.amount == 12345.0
    assert service.extra == {"note": "approx"}
