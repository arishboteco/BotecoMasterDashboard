"""Tests for sales repository interface and default implementation."""

from typing import Any, Dict, List

from repositories.sales_repository import (
    DatabaseSalesRepository,
    SalesRepository,
    get_sales_repository,
)


class FakeSalesRepository:
    """Test double implementing SalesRepository shape."""

    def get_daily_summary(self, location_id: int, date: str) -> Dict[str, Any] | None:
        return {"location_id": location_id, "date": date}

    def get_summaries_for_date_range(
        self,
        location_id: int,
        start_date: str,
        end_date: str,
    ) -> List[Dict[str, Any]]:
        return [
            {"location_id": location_id, "date": start_date},
            {"location_id": location_id, "date": end_date},
        ]

    def get_summaries_for_date_range_multi(
        self,
        location_ids: List[int],
        start_date: str,
        end_date: str,
    ) -> List[Dict[str, Any]]:
        return [
            {"location_id": location_ids[0], "date": start_date},
            {"location_id": location_ids[-1], "date": end_date},
        ]

    def save_daily_summary(self, location_id: int, data: Dict[str, Any]) -> int:
        return location_id + int(data.get("offset", 0))

    def delete_daily_summary_for_location_date(self, location_id: int, date: str) -> bool:
        return bool(location_id and date)


def test_sales_repository_protocol_runtime_shape_with_fake_repo():
    fake_repo = FakeSalesRepository()

    assert isinstance(fake_repo, SalesRepository)


def test_get_sales_repository_returns_database_implementation():
    repo = get_sales_repository()

    assert isinstance(repo, DatabaseSalesRepository)
    assert isinstance(repo, SalesRepository)


def test_database_sales_repository_delegates_calls(monkeypatch):
    calls: dict[str, tuple[Any, ...]] = {}

    def fake_get_daily_summary(location_id: int, date: str):
        calls["get_daily_summary"] = (location_id, date)
        return {"id": 1}

    def fake_get_summaries_for_date_range(location_id: int, start_date: str, end_date: str):
        calls["get_summaries_for_date_range"] = (location_id, start_date, end_date)
        return [{"id": 2}]

    def fake_get_summaries_for_date_range_multi(
        location_ids: List[int],
        start_date: str,
        end_date: str,
    ):
        calls["get_summaries_for_date_range_multi"] = (location_ids, start_date, end_date)
        return [{"id": 3}]

    def fake_save_daily_summary(location_id: int, data: Dict[str, Any]):
        calls["save_daily_summary"] = (location_id, data)
        return 99

    def fake_delete_daily_summary_for_location_date(location_id: int, date: str):
        calls["delete_daily_summary_for_location_date"] = (location_id, date)
        return True

    monkeypatch.setattr(
        "repositories.sales_repository.database.get_daily_summary", fake_get_daily_summary
    )
    monkeypatch.setattr(
        "repositories.sales_repository.database.get_summaries_for_date_range",
        fake_get_summaries_for_date_range,
    )
    monkeypatch.setattr(
        "repositories.sales_repository.database.get_summaries_for_date_range_multi",
        fake_get_summaries_for_date_range_multi,
    )
    monkeypatch.setattr(
        "repositories.sales_repository.database.save_daily_summary", fake_save_daily_summary
    )
    monkeypatch.setattr(
        "repositories.sales_repository.database.delete_daily_summary_for_location_date",
        fake_delete_daily_summary_for_location_date,
    )

    repo = DatabaseSalesRepository()

    assert repo.get_daily_summary(7, "2026-04-20") == {"id": 1}
    assert repo.get_summaries_for_date_range(7, "2026-04-01", "2026-04-20") == [{"id": 2}]
    assert repo.get_summaries_for_date_range_multi([7, 8], "2026-04-01", "2026-04-20") == [
        {"id": 3}
    ]
    assert repo.save_daily_summary(7, {"net_sales": 123.45}) == 99
    assert repo.delete_daily_summary_for_location_date(7, "2026-04-20") is True

    assert calls["get_daily_summary"] == (7, "2026-04-20")
    assert calls["get_summaries_for_date_range"] == (7, "2026-04-01", "2026-04-20")
    assert calls["get_summaries_for_date_range_multi"] == ([7, 8], "2026-04-01", "2026-04-20")
    assert calls["save_daily_summary"] == (7, {"net_sales": 123.45})
    assert calls["delete_daily_summary_for_location_date"] == (7, "2026-04-20")
