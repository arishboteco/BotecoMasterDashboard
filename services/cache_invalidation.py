"""Centralized cache invalidation helpers for post-import flows."""

from __future__ import annotations

import tabs.analytics_tab as analytics_tab
import tabs.report_tab as report_tab
from database_reads import clear_location_cache


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
