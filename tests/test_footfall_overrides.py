"""Tests for the manual footfall override repository, service, and read merge."""

from __future__ import annotations

from typing import Tuple

import database
from repositories.footfall_override_repository import (
    DatabaseFootfallOverrideRepository,
    FootfallOverrideRepository,
    get_footfall_override_repository,
)
from services.footfall_override_service import (
    OVERRIDE_ONLY_FLAG,
    apply_override_to_single,
    apply_overrides,
)


def _new_outlet(name: str) -> int:
    """Insert a fresh outlet and return its id (avoids cache_data stickiness)."""
    with database.db_connection() as conn:
        cur = conn.execute(
            "INSERT INTO locations (name) VALUES (?)",
            (name,),
        )
        conn.commit()
        return int(cur.lastrowid)


def _insert_summary(
    location_id: int,
    date: str,
    *,
    covers: int = 0,
    lunch_covers: int | None = None,
    dinner_covers: int | None = None,
    net_total: float = 0.0,
) -> int:
    with database.db_connection() as conn:
        cur = conn.execute(
            """
            INSERT INTO daily_summaries
                (location_id, date, covers, lunch_covers, dinner_covers, net_total)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (location_id, date, covers, lunch_covers, dinner_covers, net_total),
        )
        conn.commit()
        return int(cur.lastrowid)


# ─── Repository ─────────────────────────────────────────────────────────────


class TestFootfallOverrideRepository:
    def test_protocol_runtime_shape(self):
        assert isinstance(DatabaseFootfallOverrideRepository(), FootfallOverrideRepository)

    def test_factory_returns_database_implementation(self, initialized_db):
        repo = get_footfall_override_repository()
        assert isinstance(repo, DatabaseFootfallOverrideRepository)
        assert isinstance(repo, FootfallOverrideRepository)

    def test_get_returns_none_when_missing(self, initialized_db):
        repo = DatabaseFootfallOverrideRepository()
        loc_id = _new_outlet("Repo None Outlet")
        assert repo.get(loc_id, "2026-04-20") is None

    def test_upsert_creates_row(self, initialized_db):
        repo = DatabaseFootfallOverrideRepository()
        loc_id = _new_outlet("Repo Create Outlet")
        repo.upsert(
            loc_id,
            "2026-04-20",
            lunch_covers=42,
            dinner_covers=31,
            note="manual count",
            edited_by="alice",
        )
        row = repo.get(loc_id, "2026-04-20")
        assert row is not None
        assert row["lunch_covers"] == 42
        assert row["dinner_covers"] == 31
        assert row["note"] == "manual count"
        assert row["edited_by"] == "alice"

    def test_upsert_overwrites_existing_row(self, initialized_db):
        repo = DatabaseFootfallOverrideRepository()
        loc_id = _new_outlet("Repo Overwrite Outlet")
        repo.upsert(
            loc_id, "2026-04-20", lunch_covers=10, dinner_covers=20,
            note=None, edited_by="alice",
        )
        repo.upsert(
            loc_id, "2026-04-20", lunch_covers=15, dinner_covers=None,
            note="revised", edited_by="bob",
        )
        row = repo.get(loc_id, "2026-04-20")
        assert row["lunch_covers"] == 15
        assert row["dinner_covers"] is None
        assert row["note"] == "revised"
        assert row["edited_by"] == "bob"

    def test_get_for_range_filters_by_outlet_and_date(self, initialized_db):
        repo = DatabaseFootfallOverrideRepository()
        loc_a = _new_outlet("Range Outlet A")
        loc_b = _new_outlet("Range Outlet B")
        repo.upsert(loc_a, "2026-04-19", lunch_covers=5, dinner_covers=5,
                    note=None, edited_by="alice")
        repo.upsert(loc_a, "2026-04-20", lunch_covers=6, dinner_covers=6,
                    note=None, edited_by="alice")
        repo.upsert(loc_b, "2026-04-20", lunch_covers=7, dinner_covers=7,
                    note=None, edited_by="alice")
        repo.upsert(loc_a, "2026-04-21", lunch_covers=8, dinner_covers=8,
                    note=None, edited_by="alice")

        result = repo.get_for_range([loc_a], "2026-04-20", "2026-04-21")
        assert {(r["location_id"], r["date"]) for r in result} == {
            (loc_a, "2026-04-20"),
            (loc_a, "2026-04-21"),
        }

    def test_delete_returns_false_when_missing(self, initialized_db):
        repo = DatabaseFootfallOverrideRepository()
        loc_id = _new_outlet("Repo Delete Missing")
        assert repo.delete(loc_id, "2026-04-20") is False

    def test_delete_removes_row(self, initialized_db):
        repo = DatabaseFootfallOverrideRepository()
        loc_id = _new_outlet("Repo Delete Outlet")
        repo.upsert(loc_id, "2026-04-20", lunch_covers=5, dinner_covers=5,
                    note=None, edited_by="alice")
        assert repo.delete(loc_id, "2026-04-20") is True
        assert repo.get(loc_id, "2026-04-20") is None


# ─── Merge service ───────────────────────────────────────────────────────────


class TestApplyOverrides:
    def test_no_overrides_returns_input_unchanged(self, initialized_db):
        loc_id = _new_outlet("Service Noop Outlet")
        rows = [
            {"location_id": loc_id, "date": "2026-04-20", "covers": 50,
             "lunch_covers": 20, "dinner_covers": 30, "net_total": 1000.0},
        ]
        out = apply_overrides(rows, [loc_id], "2026-04-20", "2026-04-20")
        assert out == rows

    def test_overlay_replaces_legs_and_recomputes_total(self, initialized_db):
        loc_id = _new_outlet("Service Overlay Outlet")
        repo = get_footfall_override_repository()
        repo.upsert(
            loc_id, "2026-04-20", lunch_covers=42, dinner_covers=31,
            note=None, edited_by="alice",
        )
        rows = [
            {"location_id": loc_id, "date": "2026-04-20", "covers": 50,
             "lunch_covers": 20, "dinner_covers": 30, "net_total": 730.0},
        ]
        out = apply_overrides(rows, [loc_id], "2026-04-20", "2026-04-20")
        assert len(out) == 1
        assert out[0]["lunch_covers"] == 42
        assert out[0]["dinner_covers"] == 31
        assert out[0]["covers"] == 73
        # APC recomputed: net_total 730 / 73 covers = 10
        assert out[0]["apc"] == 10.0

    def test_partial_override_falls_back_to_pos_for_other_leg(self, initialized_db):
        loc_id = _new_outlet("Service Partial Outlet")
        repo = get_footfall_override_repository()
        repo.upsert(
            loc_id, "2026-04-20", lunch_covers=42, dinner_covers=None,
            note=None, edited_by="alice",
        )
        rows = [
            {"location_id": loc_id, "date": "2026-04-20", "covers": 50,
             "lunch_covers": 20, "dinner_covers": 30, "net_total": 0.0},
        ]
        out = apply_overrides(rows, [loc_id], "2026-04-20", "2026-04-20")
        assert out[0]["lunch_covers"] == 42
        # Dinner falls through to POS value
        assert out[0]["dinner_covers"] == 30
        assert out[0]["covers"] == 72

    def test_synthetic_row_injected_when_no_pos_data(self, initialized_db):
        loc_id = _new_outlet("Service Synthetic Outlet")
        repo = get_footfall_override_repository()
        repo.upsert(
            loc_id, "2026-04-20", lunch_covers=10, dinner_covers=15,
            note=None, edited_by="alice",
        )
        out = apply_overrides([], [loc_id], "2026-04-20", "2026-04-20")
        assert len(out) == 1
        synth = out[0]
        assert synth["location_id"] == loc_id
        assert synth["date"] == "2026-04-20"
        assert synth["covers"] == 25
        assert synth["lunch_covers"] == 10
        assert synth["dinner_covers"] == 15
        assert synth["net_total"] == 0.0
        assert synth["categories"] == []
        assert synth["services"] == []
        assert synth.get(OVERRIDE_ONLY_FLAG) is True

    def test_apply_override_to_single_returns_none_for_missing(self, initialized_db):
        loc_id = _new_outlet("Single Missing Outlet")
        out = apply_override_to_single(None, loc_id, "2026-04-20")
        assert out is None

    def test_apply_override_to_single_builds_synthetic(self, initialized_db):
        loc_id = _new_outlet("Single Synthetic Outlet")
        repo = get_footfall_override_repository()
        repo.upsert(
            loc_id, "2026-04-20", lunch_covers=8, dinner_covers=12,
            note=None, edited_by="alice",
        )
        out = apply_override_to_single(None, loc_id, "2026-04-20")
        assert out is not None
        assert out["covers"] == 20
        assert out.get(OVERRIDE_ONLY_FLAG) is True


# ─── End-to-end through database read facade ────────────────────────────────


def _seed_outlet_with_override(
    name: str, *, summary: bool = True
) -> Tuple[int, str]:
    loc_id = _new_outlet(name)
    date_str = "2026-04-20"
    if summary:
        _insert_summary(
            loc_id,
            date_str,
            covers=50,
            lunch_covers=20,
            dinner_covers=30,
            net_total=1000.0,
        )
    repo = get_footfall_override_repository()
    repo.upsert(
        loc_id, date_str, lunch_covers=42, dinner_covers=31,
        note=None, edited_by="alice",
    )
    return loc_id, date_str


class TestReadFacadeMerge:
    def test_get_daily_summary_reflects_override(self, initialized_db):
        loc_id, date_str = _seed_outlet_with_override("Read Daily Outlet")
        result = database.get_daily_summary(loc_id, date_str)
        assert result is not None
        assert result["covers"] == 73
        assert result["lunch_covers"] == 42
        assert result["dinner_covers"] == 31

    def test_get_daily_summary_synthetic_when_no_pos_row(self, initialized_db):
        loc_id, date_str = _seed_outlet_with_override(
            "Read Synthetic Outlet", summary=False
        )
        result = database.get_daily_summary(loc_id, date_str)
        assert result is not None
        assert result["covers"] == 73
        assert result["lunch_covers"] == 42
        assert result["dinner_covers"] == 31
        assert result["net_total"] == 0.0

    def test_get_summaries_for_date_range_multi_includes_synthetic(self, initialized_db):
        loc_id = _new_outlet("Range Synthetic Outlet")
        # POS row for one day, override-only row for another day
        _insert_summary(
            loc_id,
            "2026-04-20",
            covers=50,
            lunch_covers=20,
            dinner_covers=30,
            net_total=1000.0,
        )
        repo = get_footfall_override_repository()
        repo.upsert(
            loc_id, "2026-04-21", lunch_covers=10, dinner_covers=15,
            note=None, edited_by="alice",
        )

        rows = database.get_summaries_for_date_range_multi(
            [loc_id], "2026-04-20", "2026-04-21"
        )
        assert len(rows) == 2
        by_date = {r["date"]: r for r in rows}
        assert by_date["2026-04-20"]["covers"] == 50
        assert by_date["2026-04-21"]["covers"] == 25
        assert by_date["2026-04-21"][OVERRIDE_ONLY_FLAG] is True

    def test_clearing_override_restores_pos_values(self, initialized_db):
        loc_id, date_str = _seed_outlet_with_override("Clear Override Outlet")
        repo = get_footfall_override_repository()
        repo.delete(loc_id, date_str)
        result = database.get_daily_summary(loc_id, date_str)
        assert result is not None
        assert result["covers"] == 50
        assert result["lunch_covers"] == 20
        assert result["dinner_covers"] == 30


# ─── Cache invalidation helper smoke test ──────────────────────────────────


def test_invalidate_footfall_caches_runs_without_error(monkeypatch):
    """Smoke: helper should chain into report/analytics invalidators."""
    from services import cache_invalidation

    calls = {"reports": 0, "analytics": 0, "loc": []}
    monkeypatch.setattr(
        cache_invalidation, "invalidate_reports", lambda: calls.__setitem__(
            "reports", calls["reports"] + 1
        )
    )
    monkeypatch.setattr(
        cache_invalidation, "invalidate_analytics", lambda: calls.__setitem__(
            "analytics", calls["analytics"] + 1
        )
    )
    monkeypatch.setattr(
        cache_invalidation,
        "invalidate_location_reads",
        lambda lid: calls["loc"].append(lid),
    )

    cache_invalidation.invalidate_footfall_caches([1, 2])
    assert calls["reports"] == 1
    assert calls["analytics"] == 1
    assert calls["loc"] == [1, 2]
