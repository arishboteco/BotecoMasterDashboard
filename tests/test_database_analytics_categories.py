"""Tests for category aggregation behavior in analytics queries."""

import database
import database_analytics
import database_reads


def test_get_category_sales_returns_detailed_categories_supabase(monkeypatch):
    class _Query:
        def __init__(self, rows):
            self._rows = rows

        def select(self, _cols):
            return self

        def in_(self, _col, _vals):
            return self

        def gte(self, _col, _val):
            return self

        def lte(self, _col, _val):
            return self

        def execute(self):
            return type("R", (), {"data": self._rows})

    class _Client:
        def __init__(self, rows):
            self._rows = rows

        def table(self, _name):
            return _Query(self._rows)

    rows = [
        {
            "category_name": "Sake & Soju",
            "group_name": "Liquor",
            "normalized_category": "Liquor",
            "net_amount": 410.0,
            "qty": 2,
        },
        {
            "category_name": "Red Wine",
            "group_name": "Liquor",
            "normalized_category": "Liquor",
            "net_amount": 590.0,
            "qty": 1,
        },
        {
            "category_name": "Brazilian Bowls",
            "group_name": "Food - PFA",
            "normalized_category": "Food",
            "net_amount": 2520.0,
            "qty": 3,
        },
    ]

    monkeypatch.setattr(database, "use_supabase", lambda: True)
    monkeypatch.setattr(database, "get_supabase_client", lambda: _Client(rows))

    out = database_analytics.get_category_sales_for_date_range([1], "2026-05-07", "2026-05-07")

    assert out == [
        {"category": "Brazilian Bowls", "amount": 2520.0, "qty": 3},
        {"category": "Red Wine", "amount": 590.0, "qty": 1},
        {"category": "Sake & Soju", "amount": 410.0, "qty": 2},
    ]


def test_get_category_sales_returns_detailed_categories_sqlite(monkeypatch):
    monkeypatch.setattr(database, "use_supabase", lambda: False)
    monkeypatch.setattr(
        database_reads,
        "get_category_totals_for_date_range",
        lambda _locs, _start, _end: [
            {
                "category_name": "Original Brazilian Acai Mocktails",
                "group_name": "Soft Drink - PFA",
                "normalized_category": None,
                "net_amount": 3570.0,
                "qty": 5,
            },
            {
                "category_name": "Kombucha",
                "group_name": "Soft Drinks PFA",
                "normalized_category": None,
                "net_amount": 390.0,
                "qty": 1,
            },
        ],
    )

    out = database_analytics.get_category_sales_for_date_range([1], "2026-05-07", "2026-05-07")

    assert out == [
        {"category": "Original Brazilian Acai Mocktails", "amount": 3570.0, "qty": 5},
        {"category": "Kombucha", "amount": 390.0, "qty": 1},
    ]


def test_get_category_sales_grouped_prefers_normalized_category_supabase(monkeypatch):
    class _Query:
        def __init__(self, rows):
            self._rows = rows

        def select(self, _cols):
            return self

        def in_(self, _col, _vals):
            return self

        def gte(self, _col, _val):
            return self

        def lte(self, _col, _val):
            return self

        def execute(self):
            return type("R", (), {"data": self._rows})

    class _Client:
        def __init__(self, rows):
            self._rows = rows

        def table(self, _name):
            return _Query(self._rows)

    rows = [
        {
            "category_name": "Sake & Soju",
            "group_name": "Liquor",
            "normalized_category": "Liquor",
            "net_amount": 410.0,
            "qty": 2,
        },
        {
            "category_name": "Red Wine",
            "group_name": "Liquor",
            "normalized_category": "Liquor",
            "net_amount": 590.0,
            "qty": 1,
        },
        {
            "category_name": "Brazilian Bowls",
            "group_name": "Food - PFA",
            "normalized_category": "Food",
            "net_amount": 2520.0,
            "qty": 3,
        },
    ]

    monkeypatch.setattr(database, "use_supabase", lambda: True)
    monkeypatch.setattr(database, "get_supabase_client", lambda: _Client(rows))

    out = database_analytics.get_category_sales_grouped_for_date_range(
        [1], "2026-05-07", "2026-05-07"
    )

    assert out == [
        {"category": "Food", "amount": 2520.0, "qty": 3},
        {"category": "Liquor", "amount": 1000.0, "qty": 3},
    ]
