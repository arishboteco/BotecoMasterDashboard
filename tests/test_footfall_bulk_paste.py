"""Tests for footfall bulk paste parsing and apply helpers."""

from __future__ import annotations

from tabs.footfall_tab import (
    _apply_bulk_overrides,
    _group_bulk_rows_by_date,
    _normalize_bulk_rows,
    _parse_bulk_footfall_text,
)


def test_parse_bulk_rows_accepts_tsv_headers_case_insensitive() -> None:
    text = "date\tbrand\tservice\tcovers\nWed, 29 April 2026\tBoteco\tLunch\t10\n"
    parsed = _parse_bulk_footfall_text(text)
    assert parsed.required_headers_present is True
    assert len(parsed.rows) == 1


def test_parse_bulk_rows_falls_back_to_csv() -> None:
    text = "Date,Brand,Service,Covers\nWed, 29 April 2026,Boteco,Dinner,12\n"
    parsed = _parse_bulk_footfall_text(text)
    assert parsed.required_headers_present is True
    assert parsed.rows[0]["service"] == "Dinner"


def test_normalize_row_rejects_invalid_service_and_covers() -> None:
    rows = [{"Date": "Wed, 29 April 2026", "Service": "Brunch", "Covers": "abc"}]
    normalized, invalid = _normalize_bulk_rows(rows)
    assert normalized == []
    assert len(invalid) == 1


def test_group_rows_merges_lunch_and_dinner_by_date_last_wins() -> None:
    normalized = [
        {"date": "2026-04-29", "service": "lunch", "covers": 10},
        {"date": "2026-04-29", "service": "lunch", "covers": 11},
        {"date": "2026-04-29", "service": "dinner", "covers": 12},
    ]
    grouped = _group_bulk_rows_by_date(normalized)
    assert grouped == [{"date": "2026-04-29", "lunch_covers": 11, "dinner_covers": 12}]


def test_apply_bulk_rows_skips_existing_and_creates_missing(initialized_db) -> None:
    from repositories.footfall_override_repository import get_footfall_override_repository

    repo = get_footfall_override_repository()
    location_id = 1
    repo.upsert(
        location_id,
        "2026-04-29",
        lunch_covers=10,
        dinner_covers=20,
        note=None,
        edited_by="seed",
    )

    summary = _apply_bulk_overrides(
        location_id=location_id,
        edited_by="alice",
        grouped_rows=[
            {"date": "2026-04-29", "lunch_covers": 10, "dinner_covers": 20},
            {"date": "2026-04-30", "lunch_covers": 30, "dinner_covers": 40},
        ],
    )
    assert summary["created"] == 1
    assert summary["skipped_existing"] == 1
