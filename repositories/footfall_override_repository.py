"""Footfall override repository — manual lunch/dinner cover entries by outlet+date."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

import database

TABLE_NAME = "footfall_overrides"


@runtime_checkable
class FootfallOverrideRepository(Protocol):
    """Repository interface for manual footfall overrides."""

    def get(self, location_id: int, date: str) -> Optional[Dict[str, Any]]: ...

    def get_for_range(
        self,
        location_ids: List[int],
        start_date: str,
        end_date: str,
    ) -> List[Dict[str, Any]]: ...

    def upsert(
        self,
        location_id: int,
        date: str,
        *,
        lunch_covers: Optional[int],
        dinner_covers: Optional[int],
        note: Optional[str],
        edited_by: Optional[str],
    ) -> None: ...

    def delete(self, location_id: int, date: str) -> bool: ...


class DatabaseFootfallOverrideRepository:
    """SQLite-backed implementation of FootfallOverrideRepository."""

    def get(self, location_id: int, date: str) -> Optional[Dict[str, Any]]:
        with database.db_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT id, location_id, date, lunch_covers, dinner_covers,
                       note, edited_by, edited_at
                FROM footfall_overrides
                WHERE location_id = ? AND date = ?
                """,
                (location_id, date),
            )
            row = cur.fetchone()
        return dict(row) if row else None

    def get_for_range(
        self,
        location_ids: List[int],
        start_date: str,
        end_date: str,
    ) -> List[Dict[str, Any]]:
        if not location_ids:
            return []
        placeholders = ",".join("?" * len(location_ids))
        with database.db_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                f"""
                SELECT id, location_id, date, lunch_covers, dinner_covers,
                       note, edited_by, edited_at
                FROM footfall_overrides
                WHERE location_id IN ({placeholders})
                  AND date >= ? AND date <= ?
                ORDER BY date, location_id
                """,
                (*location_ids, start_date, end_date),
            )
            rows = cur.fetchall()
        return [dict(r) for r in rows]

    def upsert(
        self,
        location_id: int,
        date: str,
        *,
        lunch_covers: Optional[int],
        dinner_covers: Optional[int],
        note: Optional[str],
        edited_by: Optional[str],
    ) -> None:
        with database.db_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO footfall_overrides
                    (location_id, date, lunch_covers, dinner_covers, note,
                     edited_by, edited_at)
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
        with database.db_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "DELETE FROM footfall_overrides WHERE location_id = ? AND date = ?",
                (location_id, date),
            )
            conn.commit()
            return cur.rowcount > 0


class SupabaseFootfallOverrideRepository:
    """Supabase-backed implementation of FootfallOverrideRepository."""

    def _client(self) -> Any:
        client = database.get_supabase_client()
        if client is None:
            raise RuntimeError("Supabase client not available")
        return client

    def get(self, location_id: int, date: str) -> Optional[Dict[str, Any]]:
        result = (
            self._client()
            .table(TABLE_NAME)
            .select("id,location_id,date,lunch_covers,dinner_covers,note,edited_by,edited_at")
            .eq("location_id", location_id)
            .eq("date", date)
            .execute()
        )
        rows = result.data or []
        return dict(rows[0]) if rows else None

    def get_for_range(
        self,
        location_ids: List[int],
        start_date: str,
        end_date: str,
    ) -> List[Dict[str, Any]]:
        if not location_ids:
            return []
        result = (
            self._client()
            .table(TABLE_NAME)
            .select("id,location_id,date,lunch_covers,dinner_covers,note,edited_by,edited_at")
            .in_("location_id", location_ids)
            .gte("date", start_date)
            .lte("date", end_date)
            .order("date")
            .execute()
        )
        return [dict(row) for row in (result.data or [])]

    def upsert(
        self,
        location_id: int,
        date: str,
        *,
        lunch_covers: Optional[int],
        dinner_covers: Optional[int],
        note: Optional[str],
        edited_by: Optional[str],
    ) -> None:
        row = {
            "location_id": location_id,
            "date": date,
            "lunch_covers": lunch_covers,
            "dinner_covers": dinner_covers,
            "note": note,
            "edited_by": edited_by,
        }
        self._client().table(TABLE_NAME).upsert(row, on_conflict="location_id,date").execute()

    def delete(self, location_id: int, date: str) -> bool:
        result = (
            self._client()
            .table(TABLE_NAME)
            .delete()
            .eq("location_id", location_id)
            .eq("date", date)
            .execute()
        )
        return bool(result.data)


def get_footfall_override_repository() -> FootfallOverrideRepository:
    """Factory returning the default footfall override repository implementation."""
    if database.use_supabase():
        return SupabaseFootfallOverrideRepository()
    return DatabaseFootfallOverrideRepository()
