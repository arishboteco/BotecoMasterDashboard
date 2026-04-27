"""Tests for manual footfall overrides."""

from __future__ import annotations

from types import SimpleNamespace

import database
import database_analytics
import database_reads


def _insert_summary(
    location_id: int,
    date_str: str,
    *,
    lunch_covers: int = 5,
    dinner_covers: int = 7,
    net_total: float = 1200.0,
) -> None:
    with database.db_connection() as conn:
        conn.execute(
            """
            INSERT INTO daily_summaries (
                location_id, date, covers, lunch_covers, dinner_covers,
                gross_total, net_total, cash_sales
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                location_id,
                date_str,
                lunch_covers + dinner_covers,
                lunch_covers,
                dinner_covers,
                net_total,
                net_total,
                net_total,
            ),
        )
        conn.commit()


def test_repository_upsert_and_delete(initialized_db):
    from repositories.footfall_override_repository import get_footfall_override_repository

    repo = get_footfall_override_repository()

    repo.upsert(
        1,
        "2026-04-20",
        lunch_covers=42,
        dinner_covers=None,
        note="POS missed lunch pax",
        edited_by="manager@example.com",
    )
    row = repo.get(1, "2026-04-20")

    assert row is not None
    assert row["lunch_covers"] == 42
    assert row["dinner_covers"] is None
    assert row["note"] == "POS missed lunch pax"
    assert row["edited_by"] == "manager@example.com"

    assert repo.delete(1, "2026-04-20") is True
    assert repo.get(1, "2026-04-20") is None


def test_single_leg_override_uses_pos_value_for_other_leg(initialized_db):
    from repositories.footfall_override_repository import get_footfall_override_repository

    _insert_summary(1, "2026-04-20", lunch_covers=5, dinner_covers=7)
    get_footfall_override_repository().upsert(
        1,
        "2026-04-20",
        lunch_covers=42,
        dinner_covers=None,
        note=None,
        edited_by="manager@example.com",
    )

    row = database_reads.get_daily_summary(1, "2026-04-20")

    assert row is not None
    assert row["lunch_covers"] == 42
    assert row["dinner_covers"] == 7
    assert row["covers"] == 49
    assert row.get("_override_only") is None


def test_override_without_pos_data_injects_synthetic_summary_row(initialized_db):
    from repositories.footfall_override_repository import get_footfall_override_repository

    get_footfall_override_repository().upsert(
        1,
        "2026-04-21",
        lunch_covers=10,
        dinner_covers=None,
        note="Manual event count",
        edited_by="manager@example.com",
    )

    rows = database_reads.get_summaries_for_date_range_multi([1], "2026-04-21", "2026-04-21")

    assert len(rows) == 1
    row = rows[0]
    assert row["location_id"] == 1
    assert row["date"] == "2026-04-21"
    assert row["lunch_covers"] == 10
    assert row["dinner_covers"] == 0
    assert row["covers"] == 10
    assert row["net_total"] == 0
    assert row["categories"] == []
    assert row["services"] == []
    assert row["_override_only"] is True


def test_override_only_date_appears_in_daily_sales_analytics(initialized_db):
    from repositories.footfall_override_repository import get_footfall_override_repository

    get_footfall_override_repository().upsert(
        1,
        "2026-04-22",
        lunch_covers=10,
        dinner_covers=3,
        note=None,
        edited_by="manager@example.com",
    )

    rows = database_analytics.get_daily_sales_for_date_range([1], "2026-04-22", "2026-04-22")

    assert len(rows) == 1
    row = rows[0]
    assert row["date"] == "2026-04-22"
    assert row["location_id"] == 1
    assert row["net_total"] == 0
    assert row["gross_total"] == 0
    assert row["covers"] == 13
    assert row["lunch_covers"] == 10
    assert row["dinner_covers"] == 3
    assert row["_override_only"] is True


class _FakeQuery:
    def __init__(self, table_name: str, rows: dict[str, list[dict]]):
        self.table_name = table_name
        self.rows = rows
        self.filters: list[tuple[str, object]] = []
        self.in_filters: list[tuple[str, list[object]]] = []
        self.gte_filter: tuple[str, object] | None = None
        self.lte_filter: tuple[str, object] | None = None
        self.payload: dict | None = None

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, column: str, value: object):
        self.filters.append((column, value))
        return self

    def in_(self, column: str, values: list[object]):
        self.in_filters.append((column, values))
        return self

    def gte(self, column: str, value: object):
        self.gte_filter = (column, value)
        return self

    def lte(self, column: str, value: object):
        self.lte_filter = (column, value)
        return self

    def order(self, *_args, **_kwargs):
        return self

    def upsert(self, payload: dict, **_kwargs):
        self.payload = dict(payload)
        return self

    def delete(self):
        self.payload = {"_delete": True}
        return self

    def execute(self):
        table_rows = self.rows.setdefault(self.table_name, [])
        if self.payload and self.payload.get("_delete"):
            before = len(table_rows)
            self.rows[self.table_name] = [row for row in table_rows if not self._matches(row)]
            return SimpleNamespace(data=[{}] * (before - len(self.rows[self.table_name])))
        if self.payload is not None:
            replacement = dict(self.payload)
            table_rows[:] = [
                row
                for row in table_rows
                if not (
                    row.get("location_id") == replacement.get("location_id")
                    and row.get("date") == replacement.get("date")
                )
            ]
            table_rows.append(replacement)
            return SimpleNamespace(data=[replacement])
        return SimpleNamespace(data=[row for row in table_rows if self._matches(row)])

    def _matches(self, row: dict) -> bool:
        if any(row.get(column) != value for column, value in self.filters):
            return False
        if any(row.get(column) not in values for column, values in self.in_filters):
            return False
        if self.gte_filter and str(row.get(self.gte_filter[0])) < str(self.gte_filter[1]):
            return False
        if self.lte_filter and str(row.get(self.lte_filter[0])) > str(self.lte_filter[1]):
            return False
        return True


class _FakeSupabase:
    def __init__(self):
        self.rows = {"footfall_overrides": []}

    def table(self, table_name: str):
        return _FakeQuery(table_name, self.rows)


def test_supabase_repository_persists_and_reads_overrides(monkeypatch):
    from repositories.footfall_override_repository import get_footfall_override_repository

    client = _FakeSupabase()
    monkeypatch.setattr(database, "_use_supabase_override", True)
    monkeypatch.setattr(database, "get_supabase_client", lambda: client)

    repo = get_footfall_override_repository()
    repo.upsert(
        2,
        "2026-04-23",
        lunch_covers=11,
        dinner_covers=17,
        note="Manual correction",
        edited_by="manager@example.com",
    )

    assert repo.get(2, "2026-04-23") == {
        "location_id": 2,
        "date": "2026-04-23",
        "lunch_covers": 11,
        "dinner_covers": 17,
        "note": "Manual correction",
        "edited_by": "manager@example.com",
    }
    assert repo.get_for_range([2], "2026-04-01", "2026-04-30") == [
        {
            "location_id": 2,
            "date": "2026-04-23",
            "lunch_covers": 11,
            "dinner_covers": 17,
            "note": "Manual correction",
            "edited_by": "manager@example.com",
        }
    ]
    assert repo.delete(2, "2026-04-23") is True
    assert repo.get(2, "2026-04-23") is None
