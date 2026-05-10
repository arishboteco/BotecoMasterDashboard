"""Report data-loading services with coordinated in-process caching."""

from __future__ import annotations

from typing import List, Tuple

import cache_manager
import database
import scope

_REPORT_CACHE: dict = cache_manager.register("report")
_MTD_CACHE: dict = cache_manager.register("mtd")
_FOOT_CACHE: dict = cache_manager.register("foot")


def clear_report_cache() -> None:
    """Clear cached daily report, MTD, and footfall data."""
    cache_manager.invalidate("report")
    cache_manager.invalidate("mtd")
    cache_manager.invalidate("foot")


def load_report_bundle_cached(location_ids: List[int], date_str: str):
    """Load the daily report bundle with in-process cache."""
    key = (tuple(location_ids), date_str)
    if key in _REPORT_CACHE:
        return _REPORT_CACHE[key]
    outlets_bundle, summary = scope.get_daily_report_bundle(location_ids, date_str)
    _REPORT_CACHE[key] = (outlets_bundle, summary)
    return outlets_bundle, summary


def build_mtd_maps(
    location_ids: List[int], year: int, month: int, as_of_date: str
) -> Tuple[dict, dict]:
    """Build category and service month-to-date maps for the requested scope/date."""
    start_date = f"{year}-{month:02d}-01"
    cat_rows = database.get_category_sales_grouped_for_date_range(
        location_ids, start_date, as_of_date
    )
    svc_rows = database.get_service_sales_for_date_range(location_ids, start_date, as_of_date)

    mtd_cat = {
        str(r.get("category") or ""): float(r.get("amount") or r.get("total") or 0)
        for r in (cat_rows or [])
        if str(r.get("category") or "").strip()
    }
    mtd_svc = {
        str(r.get("service_type") or r.get("type") or ""): float(
            r.get("amount") or r.get("total") or 0
        )
        for r in (svc_rows or [])
        if str(r.get("service_type") or r.get("type") or "").strip()
    }
    return mtd_cat, mtd_svc


def build_mtd_maps_cached(
    location_ids: List[int], year: int, month: int, as_of_date: str
) -> Tuple[dict, dict]:
    """Build month-to-date maps with in-process cache."""
    key = (tuple(location_ids), year, month, as_of_date)
    if key in _MTD_CACHE:
        return _MTD_CACHE[key]
    res = build_mtd_maps(location_ids, year, month, as_of_date)
    _MTD_CACHE[key] = res
    return res


def get_foot_rows_cached(location_ids: List[int], year: int, month: int):
    """Load cached month footfall rows for single or multi-location scope."""
    key = (tuple(location_ids), year, month)
    if key in _FOOT_CACHE:
        return _FOOT_CACHE[key]
    if len(location_ids) > 1:
        rows = database.get_summaries_for_month_multi(location_ids, year, month)
    else:
        rows = database.get_summaries_for_month(location_ids[0], year, month)
    _FOOT_CACHE[key] = rows
    return rows
