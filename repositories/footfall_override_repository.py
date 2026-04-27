"""Footfall override repository — manual lunch/dinner cover entries by outlet+date.

Routes to Supabase when `database.use_supabase()` is True; otherwise reads/writes
the local SQLite `footfall_overrides` table. The table is created automatically on
SQLite via `database.init_database()`. On Supabase the table must be created
manually via the SQL migration in `db/migrations/footfall_overrides.sql` — until
that is applied, all reads return empty and writes log a warning so the rest of
the app continues to function.
"""

from __future__ import annotations

import sqlite3
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

import database
from boteco_logger import get_logger

logger = get_logger(__name__)

SUPABASE_FOOTFALL_OVERRIDES = "footfall_overrides"

# Postgres / Supabase error code for "relation does not exist" — matches the
# REST surfacing of `42P01` from PostgREST.
_TABLE_MISSING_HINTS = ("42P01", "does not exist", "no such table")


def _is_table_missing_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return any(hint.lower() in msg for hint in _TABLE_MISSING_HINTS)


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
    """Repository backed by Supabase in production and SQLite in local/dev."""

    # ── Supabase branch ─────────────────────────────────────────────────────

    def _supabase(self):
        if not database.use_supabase():
            return None
        return database.get_supabase_client()

    def _supabase_get(
        self, location_id: int, date: str
    ) -> Optional[Dict[str, Any]]:
        client = self._supabase()
        if client is None:
            return None
        try:
            result = (
                client.table(SUPABASE_FOOTFALL_OVERRIDES)
                .select("*")
                .eq("location_id", location_id)
                .eq("date", date)
                .limit(1)
                .execute()
            )
        except Exception as ex:
            if _is_table_missing_error(ex):
                logger.warning(
                    "Supabase table '%s' is missing — apply "
                    "db/migrations/footfall_overrides.sql to enable footfall overrides.",
                    SUPABASE_FOOTFALL_OVERRIDES,
                )
                return None
            raise
        rows = result.data or []
        return dict(rows[0]) if rows else None

    def _supabase_get_range(
        self,
        location_ids: List[int],
        start_date: str,
        end_date: str,
    ) -> List[Dict[str, Any]]:
        client = self._supabase()
        if client is None:
            return []
        try:
            result = (
                client.table(SUPABASE_FOOTFALL_OVERRIDES)
                .select("*")
                .in_("location_id", location_ids)
                .gte("date", start_date)
                .lte("date", end_date)
                .order("date")
                .execute()
            )
        except Exception as ex:
            if _is_table_missing_error(ex):
                logger.warning(
                    "Supabase table '%s' is missing — footfall overrides "
                    "disabled until the migration is applied.",
                    SUPABASE_FOOTFALL_OVERRIDES,
                )
                return []
            raise
        return [dict(r) for r in (result.data or [])]

    def _supabase_upsert(
        self,
        location_id: int,
        date: str,
        *,
        lunch_covers: Optional[int],
        dinner_covers: Optional[int],
        note: Optional[str],
        edited_by: Optional[str],
    ) -> None:
        client = self._supabase()
        if client is None:
            return
        payload: Dict[str, Any] = {
            "location_id": location_id,
            "date": date,
            "lunch_covers": lunch_covers,
            "dinner_covers": dinner_covers,
            "note": note,
            "edited_by": edited_by,
        }
        try:
            client.table(SUPABASE_FOOTFALL_OVERRIDES).upsert(
                payload, on_conflict="location_id,date"
            ).execute()
        except Exception as ex:
            if _is_table_missing_error(ex):
                logger.error(
                    "Cannot save footfall override — Supabase table '%s' is "
                    "missing. Apply db/migrations/footfall_overrides.sql.",
                    SUPABASE_FOOTFALL_OVERRIDES,
                )
                raise RuntimeError(
                    "Footfall override storage is not provisioned on Supabase. "
                    "Ask an admin to run db/migrations/footfall_overrides.sql."
                ) from ex
            raise

    def _supabase_delete(self, location_id: int, date: str) -> bool:
        client = self._supabase()
        if client is None:
            return False
        try:
            result = (
                client.table(SUPABASE_FOOTFALL_OVERRIDES)
                .delete()
                .eq("location_id", location_id)
                .eq("date", date)
                .execute()
            )
        except Exception as ex:
            if _is_table_missing_error(ex):
                logger.warning(
                    "Supabase table '%s' is missing — nothing to delete.",
                    SUPABASE_FOOTFALL_OVERRIDES,
                )
                return False
            raise
        return bool(result.data)

    # ── SQLite branch ───────────────────────────────────────────────────────

    def _sqlite_get(self, location_id: int, date: str) -> Optional[Dict[str, Any]]:
        try:
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
        except sqlite3.OperationalError as ex:
            if _is_table_missing_error(ex):
                logger.warning("SQLite footfall_overrides table missing: %s", ex)
                return None
            raise
        return dict(row) if row else None

    def _sqlite_get_range(
        self,
        location_ids: List[int],
        start_date: str,
        end_date: str,
    ) -> List[Dict[str, Any]]:
        placeholders = ",".join("?" * len(location_ids))
        try:
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
        except sqlite3.OperationalError as ex:
            if _is_table_missing_error(ex):
                logger.warning("SQLite footfall_overrides table missing: %s", ex)
                return []
            raise
        return [dict(r) for r in rows]

    def _sqlite_upsert(
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

    def _sqlite_delete(self, location_id: int, date: str) -> bool:
        with database.db_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "DELETE FROM footfall_overrides WHERE location_id = ? AND date = ?",
                (location_id, date),
            )
            conn.commit()
            return cur.rowcount > 0

    # ── Public API ──────────────────────────────────────────────────────────

    def get(self, location_id: int, date: str) -> Optional[Dict[str, Any]]:
        if database.use_supabase():
            return self._supabase_get(location_id, date)
        return self._sqlite_get(location_id, date)

    def get_for_range(
        self,
        location_ids: List[int],
        start_date: str,
        end_date: str,
    ) -> List[Dict[str, Any]]:
        if not location_ids:
            return []
        if database.use_supabase():
            return self._supabase_get_range(location_ids, start_date, end_date)
        return self._sqlite_get_range(location_ids, start_date, end_date)

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
        if database.use_supabase():
            self._supabase_upsert(
                location_id,
                date,
                lunch_covers=lunch_covers,
                dinner_covers=dinner_covers,
                note=note,
                edited_by=edited_by,
            )
            return
        self._sqlite_upsert(
            location_id,
            date,
            lunch_covers=lunch_covers,
            dinner_covers=dinner_covers,
            note=note,
            edited_by=edited_by,
        )

    def delete(self, location_id: int, date: str) -> bool:
        if database.use_supabase():
            return self._supabase_delete(location_id, date)
        return self._sqlite_delete(location_id, date)


def get_footfall_override_repository() -> FootfallOverrideRepository:
    """Factory returning the default footfall override repository implementation."""
    return DatabaseFootfallOverrideRepository()
