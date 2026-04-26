"""Tests for SQLite category_sales schema + synthetic-row backfill migration."""

from __future__ import annotations

import database


def test_init_database_creates_category_sales_table(initialized_db):
    _ = initialized_db
    with database.db_connection() as conn:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='category_sales'"
        ).fetchone()

    assert row is not None


def test_migrate_category_sales_from_synthetic_rows_backfills_and_is_idempotent(initialized_db):
    _ = initialized_db
    with database.db_connection() as conn:
        conn.execute(
            """
            INSERT INTO daily_summaries (location_id, date, net_total)
            VALUES (?, ?, ?)
            """,
            (1, "2026-04-20", 1234.0),
        )
        summary_id = conn.execute(
            "SELECT id FROM daily_summaries WHERE location_id = ? AND date = ?",
            (1, "2026-04-20"),
        ).fetchone()["id"]
        conn.execute(
            """
            INSERT INTO item_sales (summary_id, item_name, category, qty, amount)
            VALUES (?, ?, ?, ?, ?)
            """,
            (summary_id, "__category_row:Food", "Food", 4, 900.0),
        )
        conn.execute(
            """
            INSERT INTO item_sales (summary_id, item_name, category, qty, amount)
            VALUES (?, ?, ?, ?, ?)
            """,
            (summary_id, "Paneer Tikka", "Food", 2, 300.0),
        )
        conn.commit()

    first = database.migrate_category_sales_from_synthetic_rows()
    second = database.migrate_category_sales_from_synthetic_rows()

    assert first == {"inserted": 1, "skipped_existing": 0}
    assert second == {"inserted": 0, "skipped_existing": 1}

    with database.db_connection() as conn:
        rows = conn.execute(
            """
            SELECT summary_id, category_name, qty, net_amount, source
            FROM category_sales
            ORDER BY category_name
            """
        ).fetchall()

    assert [dict(r) for r in rows] == [
        {
            "summary_id": summary_id,
            "category_name": "Food",
            "qty": 4,
            "net_amount": 900.0,
            "source": "synthetic_backfill",
        }
    ]
