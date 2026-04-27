"""Footfall override repository interface and SQLite implementation."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

import database


@runtime_checkable
class FootfallOverrideRepository(Protocol):
    """Repository interface for manual lunch/dinner cover overrides."""

    def get(self, location_id: int, date: str) -> Optional[Dict[str, Any]]:
        """Fetch one override for a location/date."""

    def get_for_range(self, location_ids: List[int], start: str, end: str) -> List[Dict[str, Any]]:
        """Fetch overrides for locations in a date range."""

    def upsert(
        self,
        location_id: int,
        date: str,
        *,
        lunch_covers: Optional[int],
        dinner_covers: Optional[int],
        note: Optional[str],
        edited_by: str,
    ) -> None:
        """Create or replace the active override for a location/date."""

    def delete(self, location_id: int, date: str) -> bool:
        """Delete an override. Returns True when a row was removed."""


class DatabaseFootfallOverrideRepository:
    """SQLite-backed footfall override repository."""

    def get(self, location_id: int, date: str) -> Optional[Dict[str, Any]]:
        if database.use_supabase():
            # TODO: Add Supabase persistence for footfall_overrides after v1 SQLite rollout.
            return None

        with database.db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM footfall_overrides
                WHERE location_id = ? AND date = ?
                """,
                (location_id, date),
            )
            row = cursor.fetchone()
        return dict(row) if row else None

    def get_for_range(self, location_ids: List[int], start: str, end: str) -> List[Dict[str, Any]]:
        if database.use_supabase() or not location_ids:
            # TODO: Add Supabase persistence for footfall_overrides after v1 SQLite rollout.
            return []

        placeholders = ",".join("?" * len(location_ids))
        with database.db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"""
                SELECT * FROM footfall_overrides
                WHERE location_id IN ({placeholders})
                  AND date >= ? AND date <= ?
                ORDER BY date, location_id
                """,
                (*location_ids, start, end),
            )
            rows = cursor.fetchall()
        return [dict(row) for row in rows]

    def upsert(
        self,
        location_id: int,
        date: str,
        *,
        lunch_covers: Optional[int],
        dinner_covers: Optional[int],
        note: Optional[str],
        edited_by: str,
    ) -> None:
        if database.use_supabase():
            # TODO: Add Supabase persistence for footfall_overrides after v1 SQLite rollout.
            return

        with database.db_connection() as conn:
            conn.execute(
                """
                INSERT INTO footfall_overrides (
                    location_id, date, lunch_covers, dinner_covers, note, edited_by, edited_at
                )
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(location_id, date) DO UPDATE SET
                    lunch_covers = excluded.lunch_covers,
                    dinner_covers = excluded.dinner_covers,
                    note = excluded.note,
                    edited_by = excluded.edited_by,
                    edited_at = CURRENT_TIMESTAMP
                """,
                (location_id, date, lunch_covers, dinner_covers, note, edited_by),
            )
            conn.commit()

    def delete(self, location_id: int, date: str) -> bool:
        if database.use_supabase():
            # TODO: Add Supabase persistence for footfall_overrides after v1 SQLite rollout.
            return False

        with database.db_connection() as conn:
            cursor = conn.execute(
                """
                DELETE FROM footfall_overrides
                WHERE location_id = ? AND date = ?
                """,
                (location_id, date),
            )
            conn.commit()
            return cursor.rowcount > 0


def get_footfall_override_repository() -> FootfallOverrideRepository:
    """Factory returning the default footfall override repository implementation."""
    return DatabaseFootfallOverrideRepository()
