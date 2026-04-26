"""Service layer for upload preview overlap checks and import persistence."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

import config
import database
import smart_upload
import utils
from database_reads import peek_existing_net_sales_batch
from uploads.models import SmartUploadResult


@dataclass
class ImportOptions:
    """Optional overrides for import settings."""

    uploaded_by: str = "user"
    monthly_target: float | None = None
    daily_target: float | None = None
    seat_count: int | None = None


def preview_upload(
    files_payload: list[tuple[str, bytes]],
    location_id: int,
) -> SmartUploadResult:
    """Parse uploaded files into a save-ready smart upload result."""
    return smart_upload.process_smart_upload(files_payload, location_id)


def find_overlaps(upload_result: SmartUploadResult) -> list[tuple[int, str, float]]:
    """Return existing (location_id, date, net_sales) rows that will be replaced."""
    overlap_rows: list[tuple[int, str, float]] = []
    for lid, days in upload_result.location_results.items():
        valid_dates = [day.date for day in days if not day.errors]
        if not valid_dates:
            continue
        existing = peek_existing_net_sales_batch(lid, valid_dates)
        for date_str, net_val in existing.items():
            overlap_rows.append((lid, date_str, net_val))
    return overlap_rows


def import_upload(
    upload_result: SmartUploadResult,
    context: Any,
    options: ImportOptions | None = None,
) -> tuple[int, int, list[str]]:
    """Persist parsed upload result and return save counts + messages."""
    import_options = options or ImportOptions()
    loc_settings = database.get_location_settings(context.location_id)
    monthly_target = (
        import_options.monthly_target
        if import_options.monthly_target is not None
        else (
            loc_settings.get("target_monthly_sales", config.MONTHLY_TARGET)
            if loc_settings
            else config.MONTHLY_TARGET
        )
    )
    now = datetime.now()
    fallback_daily = utils.compute_daily_target(float(monthly_target), now.year, now.month)
    daily_target = (
        import_options.daily_target
        if import_options.daily_target is not None
        else (
            loc_settings.get("target_daily_sales", fallback_daily)
            if loc_settings
            else fallback_daily
        )
    )
    if import_options.seat_count is not None:
        seat_count = import_options.seat_count
    else:
        sc_setting = loc_settings.get("seat_count") if loc_settings else None
        seat_count = int(sc_setting) if sc_setting else None

    return smart_upload.save_smart_upload_results(
        upload_result,
        context.location_id,
        import_options.uploaded_by,
        monthly_target=float(monthly_target),
        daily_target=float(daily_target),
        seat_count=seat_count,
    )
