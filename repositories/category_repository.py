"""Category sales repository interface and default implementation."""

from __future__ import annotations

from typing import Any, Dict, List, Protocol, runtime_checkable

import database
from db.category_rows import CATEGORY_ROW_PREFIX
from db.table_names import SQLITE_ITEM_SALES


@runtime_checkable
class CategoryRepository(Protocol):
    """Repository interface for category-sales persistence and reads."""

    def get_category_sales_for_date_range(
        self,
        location_ids: List[int],
        start_date: str,
        end_date: str,
    ) -> List[Dict[str, Any]]:
        """Fetch aggregated category sales for one or more locations."""

    def save_category_sales(
        self,
        location_id: int,
        date: str,
        categories: List[Dict[str, Any]],
    ) -> None:
        """Persist per-day category totals for a location."""


class DatabaseCategoryRepository:
    """Category repository backed by current database facade/writes."""

    def get_category_sales_for_date_range(
        self,
        location_ids: List[int],
        start_date: str,
        end_date: str,
    ) -> List[Dict[str, Any]]:
        return database.get_category_sales_for_date_range(location_ids, start_date, end_date)

    def save_category_sales(
        self,
        location_id: int,
        date: str,
        categories: List[Dict[str, Any]],
    ) -> None:
        if database.use_supabase():
            from database_writes import delete_category_summary, save_category_summary

            client = database.get_supabase_client()
            if client is None:
                raise RuntimeError("Supabase client not available")
            delete_category_summary(client, date, location_id)
            for category in categories:
                name = str(category.get("category") or "").strip()
                if not name:
                    continue
                save_category_summary(
                    client,
                    location_id=location_id,
                    date=date,
                    category_name=name,
                    qty=int(category.get("qty", 0) or 0),
                    amount=float(category.get("amount", category.get("total", 0)) or 0),
                )
            return

        summary_id = database.save_daily_summary(location_id, {"date": date})
        with database.db_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                f"""
                DELETE FROM {SQLITE_ITEM_SALES}
                WHERE summary_id = ?
                  AND item_name LIKE ?
                """,
                (summary_id, f"{CATEGORY_ROW_PREFIX}%"),
            )
            for category in categories:
                name = str(category.get("category") or "").strip()
                if not name:
                    continue
                cur.execute(
                    f"""
                    INSERT INTO {SQLITE_ITEM_SALES} (summary_id, item_name, category, qty, amount)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        summary_id,
                        f"{CATEGORY_ROW_PREFIX}{name}",
                        name,
                        int(category.get("qty", 0) or 0),
                        float(category.get("amount", category.get("total", 0)) or 0),
                    ),
                )
            conn.commit()


def get_category_repository() -> CategoryRepository:
    """Factory returning the default category repository implementation."""
    return DatabaseCategoryRepository()
