"""Tests for category repository abstraction and default implementation."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from typing import Any, Dict, List

from repositories.category_repository import (
    CategoryRepository,
    DatabaseCategoryRepository,
    get_category_repository,
)


class FakeCategoryRepository:
    """Test double implementing CategoryRepository shape."""

    def get_category_sales_for_date_range(
        self,
        location_ids: List[int],
        start_date: str,
        end_date: str,
    ) -> List[Dict[str, Any]]:
        return [
            {"category": "Food", "amount": 100.0},
            {"location_ids": location_ids, "start": start_date, "end": end_date},
        ]

    def save_category_sales(
        self,
        location_id: int,
        date: str,
        categories: List[Dict[str, Any]],
    ) -> None:
        _ = (location_id, date, categories)


def test_category_repository_protocol_runtime_shape_with_fake_repo():
    fake_repo = FakeCategoryRepository()

    assert isinstance(fake_repo, CategoryRepository)


def test_get_category_repository_returns_database_implementation():
    repo = get_category_repository()

    assert isinstance(repo, DatabaseCategoryRepository)
    assert isinstance(repo, CategoryRepository)


def test_database_category_repository_delegates_get(monkeypatch):
    captured: Dict[str, Any] = {}

    def fake_get_category_sales_for_date_range(location_ids, start_date, end_date):
        captured["args"] = (location_ids, start_date, end_date)
        return [{"category": "Food", "total": 123.0}]

    monkeypatch.setattr(
        "repositories.category_repository.database.get_category_sales_for_date_range",
        fake_get_category_sales_for_date_range,
    )

    repo = DatabaseCategoryRepository()
    result = repo.get_category_sales_for_date_range([1, 2], "2026-04-01", "2026-04-20")

    assert result == [{"category": "Food", "total": 123.0}]
    assert captured["args"] == ([1, 2], "2026-04-01", "2026-04-20")


def test_database_category_repository_save_sqlite_updates_only_category_rows(monkeypatch):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE item_sales (
            summary_id INTEGER NOT NULL,
            item_name TEXT NOT NULL,
            category TEXT DEFAULT '',
            qty INTEGER DEFAULT 0,
            amount REAL DEFAULT 0
        )
        """
    )
    conn.execute(
        """
        INSERT INTO item_sales (summary_id, item_name, category, qty, amount)
        VALUES (10, '__category_row:Old', 'Old', 1, 50.0)
        """
    )
    conn.execute(
        """
        INSERT INTO item_sales (summary_id, item_name, category, qty, amount)
        VALUES (10, 'Paneer Tikka', 'Food', 2, 300.0)
        """
    )
    conn.commit()

    @contextmanager
    def fake_db_connection():
        yield conn

    monkeypatch.setattr("repositories.category_repository.database.use_supabase", lambda: False)
    monkeypatch.setattr(
        "repositories.category_repository.database.save_daily_summary",
        lambda location_id, data: 10,
    )
    monkeypatch.setattr(
        "repositories.category_repository.database.db_connection",
        fake_db_connection,
    )

    repo = DatabaseCategoryRepository()
    repo.save_category_sales(
        location_id=1,
        date="2026-04-20",
        categories=[
            {"category": "Food", "qty": 4, "amount": 900.0},
            {"category": "Liquor", "qty": 2, "total": 450.0},
        ],
    )

    rows = conn.execute(
        (
            "SELECT item_name, category, qty, amount "
            "FROM item_sales WHERE summary_id = 10 ORDER BY item_name"
        )
    ).fetchall()

    assert [(r["item_name"], r["category"], r["qty"], r["amount"]) for r in rows] == [
        ("Paneer Tikka", "Food", 2, 300.0),
        ("__category_row:Food", "Food", 4, 900.0),
        ("__category_row:Liquor", "Liquor", 2, 450.0),
    ]


def test_database_category_repository_save_supabase_delegates_writes(monkeypatch):
    calls: Dict[str, Any] = {"saved": []}
    fake_client = object()

    monkeypatch.setattr("repositories.category_repository.database.use_supabase", lambda: True)
    monkeypatch.setattr(
        "repositories.category_repository.database.get_supabase_client",
        lambda: fake_client,
    )

    def fake_delete_category_summary(client, date, location_id):
        calls["deleted"] = (client, date, location_id)

    def fake_save_category_summary(client, **kwargs):
        calls["saved"].append((client, kwargs))

    monkeypatch.setattr(
        "database_writes.delete_category_summary",
        fake_delete_category_summary,
    )
    monkeypatch.setattr(
        "database_writes.save_category_summary",
        fake_save_category_summary,
    )

    repo = DatabaseCategoryRepository()
    repo.save_category_sales(
        location_id=2,
        date="2026-04-21",
        categories=[
            {"category": "Food", "qty": 5, "amount": 1000.0},
            {"category": "Coffee", "qty": 3, "total": 330.0},
        ],
    )

    assert calls["deleted"] == (fake_client, "2026-04-21", 2)
    assert calls["saved"] == [
        (
            fake_client,
            {
                "location_id": 2,
                "date": "2026-04-21",
                "category_name": "Food",
                "qty": 5,
                "amount": 1000.0,
            },
        ),
        (
            fake_client,
            {
                "location_id": 2,
                "date": "2026-04-21",
                "category_name": "Coffee",
                "qty": 3,
                "amount": 330.0,
            },
        ),
    ]
