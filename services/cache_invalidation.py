"""Centralized cache invalidation helpers for post-import flows."""

from __future__ import annotations

import tabs.analytics_tab as analytics_tab
import tabs.report_tab as report_tab
from database_reads import clear_location_cache
from services import report_service


def invalidate_after_import(location_ids: list[int]) -> None:
    """Invalidate all cache groups impacted by an import."""
    for location_id in location_ids:
        invalidate_location_reads(location_id)
    invalidate_analytics()
    invalidate_reports()


def invalidate_reports() -> None:
    """Invalidate report-tab caches."""
    report_tab.clear_report_cache()


def invalidate_analytics() -> None:
    """Invalidate analytics-tab caches."""
    analytics_tab.clear_analytics_cache()


def invalidate_location_reads(location_id: int) -> None:
    """Invalidate location-scoped cached database reads."""
    clear_location_cache(location_id)


def invalidate_footfall_caches(location_id: int) -> None:
    """Invalidate caches impacted by a manual footfall override change."""
    invalidate_location_reads(location_id)
    invalidate_analytics()
    invalidate_reports()
    report_service._REPORT_CACHE.clear()
    report_service._FOOT_CACHE.clear()
    report_service._MTD_CACHE.clear()
