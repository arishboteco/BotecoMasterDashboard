"""Service layer for upload preview overlap checks and import persistence."""

from __future__ import annotations

from dataclasses import dataclass, field
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


@dataclass
class ReplacedDay:
    """One (outlet, date) that already has saved data the import will overwrite."""

    location_id: int
    location_name: str
    date: str
    existing_net: float
    incoming_net: float

    @property
    def delta(self) -> float:
        return self.incoming_net - self.existing_net


@dataclass
class OutletPlan:
    """Per-outlet summary of what an in-progress upload is about to save."""

    location_id: int
    location_name: str
    has_growth: bool = False
    has_item: bool = False
    has_comp: bool = False
    date_min: str | None = None
    date_max: str | None = None
    total_days: int = 0
    new_days: int = 0
    replace_days: int = 0
    incoming_net: float = 0.0
    coverage_gaps: list[str] = field(default_factory=list)


@dataclass
class ImportPlan:
    """Everything the Upload page needs to summarise a staged import at a glance."""

    outlets: list[OutletPlan] = field(default_factory=list)
    replaced: list[ReplacedDay] = field(default_factory=list)
    coverage_warnings: list[str] = field(default_factory=list)

    @property
    def total_days(self) -> int:
        return sum(o.total_days for o in self.outlets)

    @property
    def new_days(self) -> int:
        return sum(o.new_days for o in self.outlets)

    @property
    def replace_days(self) -> int:
        return sum(o.replace_days for o in self.outlets)

    @property
    def outlet_count(self) -> int:
        return len(self.outlets)

    @property
    def net_total(self) -> float:
        return sum(o.incoming_net for o in self.outlets)

    @property
    def has_replacements(self) -> bool:
        return self.replace_days > 0

    @property
    def has_coverage_warnings(self) -> bool:
        return bool(self.coverage_warnings)


def build_import_plan(
    upload_result: SmartUploadResult,
    overlap_rows: list[tuple[int, str, float]],
    loc_name_map: dict[int, str],
) -> ImportPlan:
    """Summarise a staged (not-yet-saved) upload for the review screen.

    Reads only what's already parsed on ``upload_result`` plus the overlap
    rows ``find_overlaps`` already computes — no additional queries.
    """
    existing_by_loc_date: dict[tuple[int, str], float] = {
        (lid, date_str): net_val for lid, date_str, net_val in overlap_rows
    }

    new_flow_meta: dict[str, Any] = getattr(upload_result, "new_flow_meta", {})
    category_by_loc: dict[int, list[dict]] = getattr(upload_result, "category_by_loc", {})
    growth_locs: set[int] = set()
    item_locs: set[int] = set(category_by_loc.keys())
    comp_locs: set[int] = set()
    for meta in new_flow_meta.values():
        loc_id = meta.get("detected_location_id")
        if loc_id is None:
            continue
        file_type = str(meta.get("file_type") or "")
        if file_type == "growth_report_day_wise":
            growth_locs.add(loc_id)
        elif file_type == "item_order_details":
            item_locs.add(loc_id)
        elif file_type == "order_comp_summary":
            comp_locs.add(loc_id)

    outlets: list[OutletPlan] = []
    replaced: list[ReplacedDay] = []
    coverage_warnings: list[str] = []

    all_loc_ids = set(upload_result.location_results.keys()) | item_locs | growth_locs | comp_locs
    for loc_id in sorted(all_loc_ids):
        loc_name = loc_name_map.get(loc_id, f"Outlet {loc_id}")
        day_results = upload_result.location_results.get(loc_id, [])
        valid_days = [d for d in day_results if not d.errors]
        dates = sorted(d.date for d in valid_days)

        plan = OutletPlan(
            location_id=loc_id,
            location_name=loc_name,
            has_growth=loc_id in growth_locs,
            has_item=loc_id in item_locs,
            has_comp=loc_id in comp_locs,
            date_min=dates[0] if dates else None,
            date_max=dates[-1] if dates else None,
            total_days=len(dates),
        )

        for day in valid_days:
            incoming_net = float(day.merged.get("net_total") or 0)
            plan.incoming_net += incoming_net
            key = (loc_id, day.date)
            if key in existing_by_loc_date:
                plan.replace_days += 1
                replaced.append(
                    ReplacedDay(
                        location_id=loc_id,
                        location_name=loc_name,
                        date=day.date,
                        existing_net=existing_by_loc_date[key],
                        incoming_net=incoming_net,
                    )
                )
            else:
                plan.new_days += 1

        item_dates = sorted(
            {row["date"] for row in category_by_loc.get(loc_id, []) if row.get("date")}
        )
        if plan.has_growth and plan.has_item and item_dates and dates:
            growth_start, growth_end = dates[0], dates[-1]
            item_start, item_end = item_dates[0], item_dates[-1]
            uncovered_before = item_start < growth_start
            uncovered_after = item_end > growth_end
            if uncovered_before or uncovered_after:
                gap_days = len({d for d in item_dates if d < growth_start or d > growth_end})
                msg = (
                    f"{loc_name}: Item Report covers {item_start} → {item_end} but the "
                    f"Growth Report only covers {growth_start} → {growth_end}. "
                    f"{gap_days} day(s) will get category data with no financial summary "
                    "or service split."
                )
                plan.coverage_gaps.append(msg)
                coverage_warnings.append(msg)

        outlets.append(plan)

    replaced.sort(key=lambda r: (-abs(r.delta), r.location_name, r.date))
    return ImportPlan(outlets=outlets, replaced=replaced, coverage_warnings=coverage_warnings)


# Short labels for the report-type column of the import-history table.
# (file_detector.KIND_LABELS is verbose — meant for the file-detection screen.)
_REPORT_TYPE_LABELS = {
    "growth_report_day_wise": "Growth Report",
    "order_comp_summary": "Comp Summary",
    "dynamic_report": "Dynamic Report",
    "item_order_details": "Item Report",
    "timing_report": "Timing Report",
    "order_summary_csv": "Order Summary",
    "flash_report": "Flash Report",
}


def report_type_label(file_type: str) -> str:
    """Human label for a detected report type slug, e.g. ``growth_report_day_wise``."""
    return _REPORT_TYPE_LABELS.get(file_type, "—")


@dataclass
class ImportBatch:
    """One uploaded file, with its day-level upload_history rows collapsed into one."""

    uploaded_at: str
    uploaded_by: str
    filename: str
    file_hash: str | None
    location_id: int
    location_name: str
    report_type: str
    period_start: str | None
    period_end: str | None
    row_count: int | None
    days_saved: int
    dates: list[str] = field(default_factory=list)
    status: str = "imported"
    validation_errors: str | None = None
    import_summary: str | None = None

    @property
    def report_label(self) -> str:
        return _REPORT_TYPE_LABELS.get(self.report_type, self.report_type or "Unknown")

    @property
    def covers_label(self) -> str:
        if not self.dates:
            return "—"
        lo, hi = min(self.dates), max(self.dates)
        return lo if lo == hi else f"{lo} → {hi}"


def _batch_key(row: dict) -> tuple:
    """Group key for collapsing day-level upload_history rows into one batch.

    Groups by file identity (hash when present, else filename), the outlet,
    who uploaded it, and the upload minute — the same file/location/uploader
    triple saved a minute apart is a distinct upload, not the same batch.
    """
    uploaded_at = str(row.get("uploaded_at") or "")
    minute = uploaded_at[:16]  # "YYYY-MM-DDTHH:MM"
    file_id = row.get("file_hash") or row.get("filename") or ""
    return (file_id, row.get("location_id"), row.get("uploaded_by"), minute)


def summarize_upload_history(
    rows: list[dict],
    loc_name_map: dict[int, str],
    limit: int = 8,
) -> list[ImportBatch]:
    """Collapse day-level upload_history rows into one row per uploaded file.

    ``upload_history`` stores one row per (date, outlet, file) — a single
    multi-month Growth Report produces dozens of rows. This groups them back
    into the file-level events a person actually cares about, newest first.
    """
    groups: dict[tuple, list[dict]] = {}
    for row in rows:
        groups.setdefault(_batch_key(row), []).append(row)

    batches: list[ImportBatch] = []
    for group_rows in groups.values():
        first = group_rows[0]
        dates = sorted({str(r.get("date")) for r in group_rows if r.get("date")})
        loc_id = first.get("location_id")
        fallback_name = first.get("detected_location_name") or f"Outlet {loc_id}"
        loc_name = loc_name_map.get(loc_id, fallback_name)
        latest_uploaded_at = max(str(r.get("uploaded_at") or "") for r in group_rows)
        batches.append(
            ImportBatch(
                uploaded_at=latest_uploaded_at,
                uploaded_by=str(first.get("uploaded_by") or ""),
                filename=str(first.get("filename") or ""),
                file_hash=first.get("file_hash"),
                location_id=loc_id,
                location_name=loc_name,
                report_type=str(first.get("file_type") or first.get("detected_report_type") or ""),
                period_start=first.get("period_start"),
                period_end=first.get("period_end"),
                row_count=first.get("row_count"),
                days_saved=len(dates),
                dates=dates,
                status=str(first.get("status") or "imported"),
                validation_errors=first.get("validation_errors"),
                import_summary=first.get("import_summary"),
            )
        )

    batches.sort(key=lambda b: b.uploaded_at, reverse=True)
    return batches[:limit]


def find_duplicate_uploads(
    new_flow_meta: dict[str, dict],
    history_rows: list[dict],
) -> list[tuple[str, str, str]]:
    """Return (filename, previous_uploaded_at, previous_uploaded_by) for repeat file hashes.

    A hash match means the exact same file content was saved before — the
    incoming upload is a genuine duplicate, not a corrected re-export (those
    would have a different hash).
    """
    seen_hashes: dict[str, dict] = {}
    for row in history_rows:
        file_hash = row.get("file_hash")
        if not file_hash:
            continue
        existing = seen_hashes.get(file_hash)
        if existing is None or str(row.get("uploaded_at") or "") > str(
            existing.get("uploaded_at") or ""
        ):
            seen_hashes[file_hash] = row

    duplicates: list[tuple[str, str, str]] = []
    for filename, meta in new_flow_meta.items():
        file_hash = meta.get("file_hash")
        if not file_hash:
            continue
        prior = seen_hashes.get(file_hash)
        if prior is not None:
            duplicates.append(
                (filename, str(prior.get("uploaded_at") or ""), str(prior.get("uploaded_by") or ""))
            )
    return duplicates


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
