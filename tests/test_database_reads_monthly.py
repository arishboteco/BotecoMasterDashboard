"""Tests for month-based summary reads in database_reads."""

from __future__ import annotations

import database_reads
import database_writes


def _save_summary(location_id: int, date_str: str, net_total: float) -> None:
    database_writes.save_daily_summary(
        location_id,
        {
            "date": date_str,
            "covers": 10,
            "gross_total": net_total,
            "net_total": net_total,
            "cash_sales": net_total,
            "card_sales": 0.0,
            "gpay_sales": 0.0,
            "zomato_sales": 0.0,
            "other_sales": 0.0,
            "categories": [],
            "services": [],
            "top_items": [],
        },
    )


def test_get_summaries_for_month_excludes_next_month_first_day(initialized_db):
    location_id = int(database_reads.get_all_locations()[0]["id"])
    _save_summary(location_id, "2026-12-31", 100.0)
    _save_summary(location_id, "2027-01-01", 200.0)

    rows = database_reads.get_summaries_for_month(location_id, 2026, 12)
    dates = [row["date"] for row in rows]

    assert "2026-12-31" in dates
    assert "2027-01-01" not in dates


def test_get_summaries_for_month_handles_february_non_leap(initialized_db):
    location_id = int(database_reads.get_all_locations()[0]["id"])
    _save_summary(location_id, "2025-02-28", 100.0)
    _save_summary(location_id, "2025-03-01", 200.0)

    rows = database_reads.get_summaries_for_month(location_id, 2025, 2)
    dates = [row["date"] for row in rows]

    assert "2025-02-28" in dates
    assert "2025-03-01" not in dates


def test_get_summaries_for_month_multi_excludes_next_month_first_day(initialized_db):
    location_id = int(database_reads.get_all_locations()[0]["id"])
    _save_summary(location_id, "2024-02-29", 100.0)
    _save_summary(location_id, "2024-03-01", 200.0)

    rows = database_reads.get_summaries_for_month_multi([location_id], 2024, 2)
    dates = [row["date"] for row in rows]

    assert "2024-02-29" in dates
    assert "2024-03-01" not in dates
