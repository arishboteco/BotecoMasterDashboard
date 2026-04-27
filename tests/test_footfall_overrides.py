"""Tests for manual footfall overrides."""

from __future__ import annotations

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


def test_delete_override_restores_pos_values(initialized_db):
    from repositories.footfall_override_repository import get_footfall_override_repository

    repo = get_footfall_override_repository()
    _insert_summary(1, "2026-04-20", lunch_covers=5, dinner_covers=7)
    repo.upsert(
        1,
        "2026-04-20",
        lunch_covers=42,
        dinner_covers=31,
        note=None,
        edited_by="manager@example.com",
    )

    repo.delete(1, "2026-04-20")
    row = database_reads.get_daily_summary(1, "2026-04-20")

    assert row is not None
    assert row["lunch_covers"] == 5
    assert row["dinner_covers"] == 7
    assert row["covers"] == 12


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
