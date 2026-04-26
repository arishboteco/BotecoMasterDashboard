"""Sales repository interface and default implementation."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

import database


@runtime_checkable
class SalesRepository(Protocol):
    """Repository interface for daily sales summaries."""

    def get_daily_summary(self, location_id: int, date: str) -> Optional[Dict[str, Any]]:
        """Fetch a single daily summary for location and date."""

    def get_summaries_for_date_range(
        self,
        location_id: int,
        start_date: str,
        end_date: str,
    ) -> List[Dict[str, Any]]:
        """Fetch summaries for a location over a date range."""

    def get_summaries_for_date_range_multi(
        self,
        location_ids: List[int],
        start_date: str,
        end_date: str,
    ) -> List[Dict[str, Any]]:
        """Fetch summaries for multiple locations over a date range."""

    def save_daily_summary(self, location_id: int, data: Dict[str, Any]) -> int:
        """Save a daily summary for a location and return summary ID."""

    def delete_daily_summary_for_location_date(self, location_id: int, date: str) -> bool:
        """Delete summary data for a location and date."""


class DatabaseSalesRepository:
    """Repository backed by existing database facade functions."""

    def get_daily_summary(self, location_id: int, date: str) -> Optional[Dict[str, Any]]:
        return database.get_daily_summary(location_id, date)

    def get_summaries_for_date_range(
        self,
        location_id: int,
        start_date: str,
        end_date: str,
    ) -> List[Dict[str, Any]]:
        return database.get_summaries_for_date_range(location_id, start_date, end_date)

    def get_summaries_for_date_range_multi(
        self,
        location_ids: List[int],
        start_date: str,
        end_date: str,
    ) -> List[Dict[str, Any]]:
        return database.get_summaries_for_date_range_multi(location_ids, start_date, end_date)

    def save_daily_summary(self, location_id: int, data: Dict[str, Any]) -> int:
        return database.save_daily_summary(location_id, data)

    def delete_daily_summary_for_location_date(self, location_id: int, date: str) -> bool:
        return database.delete_daily_summary_for_location_date(location_id, date)


def get_sales_repository() -> SalesRepository:
    """Factory returning the default sales repository implementation."""
    return DatabaseSalesRepository()
