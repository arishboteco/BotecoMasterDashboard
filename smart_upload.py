"""
Smart upload: accept any mix of Petpooja exports, auto-detect each file type,
route to the right parser, merge data by date, and return save-ready records.

NEW FLOW (primary):
  growth_report_day_wise - Growth Report Day Wise (.xlsx)  → daily_summary
  item_order_details     - Item Report With Customer/Order Details (.xlsx)  → category_summary

LEGACY FLOW (backward compatible):
  dynamic_report       - Dynamic Report CSV (per-bill order-level)
  timing_report        - Restaurant Timing Report (.xlsx)
  order_summary_csv    - Order Summary Report (.csv)
  flash_report         - POS Collection / Flash Report (.xlsx)
"""

from __future__ import annotations

import hashlib
import time
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

import boteco_logger
import config
import database
import dynamic_report_parser
import file_detector
import pos_parser
import timing_parser
from services.location_detection import detect_location_from_file
from services.location_resolver import resolve_location_id
from uploads.merge import merge_fragments_by_date
from uploads.models import DayResult, FileResult, SmartUploadResult
from uploads.parsers.flash_report import parse_flash_report
from uploads.parsers.growth_report_day_wise import parse_growth_report_day_wise
from uploads.parsers.item_report_category_summary import parse_item_report_category_summary
from uploads.parsers.order_comp_summary import parse_order_comp_summary
from uploads.parsers.order_summary import parse_order_summary_csv
from uploads.router import (
    build_restaurant_location_map,
    group_fragments_by_restaurant,
    route_tagged_fragments_by_location,
)

logger = boteco_logger.get_logger(__name__)

_PARSE_EXCEPTIONS = (
    ValueError,
    TypeError,
    KeyError,
    OSError,
    UnicodeDecodeError,
    pd.errors.ParserError,
    pd.errors.EmptyDataError,
)


def _file_hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


# ---------------------------------------------------------------------------
# New-flow processing helpers
# ---------------------------------------------------------------------------


def _detect_location_for_file(
    content: bytes,
    filename: str,
    fallback_location_id: int,
) -> Tuple[Optional[int], Optional[str], str]:
    """Auto-detect outlet from file content.

    Returns (location_id, detected_name, match_type).
    location_id is None if detection failed.
    """
    result = detect_location_from_file(content, filename)
    if result:
        return (
            result.get("location_id"),
            result.get("detected_location_name"),
            result.get("match_type", "exact"),
        )
    return None, None, "none"


def _process_new_flow_files(
    growth_files: List[Tuple[str, bytes]],
    item_files: List[Tuple[str, bytes]],
    fallback_location_id: int,
    filename_to_fr: Dict[str, FileResult],
    global_notes: List[str],
    comp_files: Optional[List[Tuple[str, bytes]]] = None,
) -> Tuple[
    Dict[int, List[Dict[str, Any]]],  # daily_rows by location_id
    Dict[int, List[Dict[str, Any]]],  # category_rows by location_id
    Dict[str, Dict[str, Any]],  # file_meta by filename
    Dict[int, Dict[str, List[Dict[str, Any]]]],  # service rows by location/date
]:
    """Parse growth and item reports, routing by auto-detected outlet.

    Returns separate dicts of daily rows and category rows keyed by location_id,
    plus per-file metadata (period, row_count, location info).
    """
    daily_by_loc: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
    cat_by_loc: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
    item_service_by_loc: Dict[int, Dict[str, List[Dict[str, Any]]]] = defaultdict(dict)
    file_meta: Dict[str, Dict[str, Any]] = {}

    # --- Growth Reports → daily_summary rows ---
    for fname, content in growth_files:
        fr = filename_to_fr.get(fname)
        loc_id, loc_name, match_type = _detect_location_for_file(
            content, fname, fallback_location_id
        )
        if loc_id is None:
            err = (
                f"Growth Report {fname}: outlet could not be detected from file content. "
                "Make sure the report contains a 'Restaurant Name:' row."
            )
            global_notes.append(err)
            if fr:
                fr.error = err
            continue

        rows, errors, meta = parse_growth_report_day_wise(content, fname, loc_id)
        meta["detected_location_id"] = loc_id
        meta["detected_location_name"] = loc_name
        meta["match_type"] = match_type
        meta["file_hash"] = _file_hash(content)
        file_meta[fname] = meta

        if errors:
            for e in errors:
                global_notes.append(e)
            if fr:
                fr.error = "; ".join(errors)
            continue

        daily_by_loc[loc_id].extend(rows)
        if fr:
            fr.notes.append(f"Parsed {len(rows)} day(s) → {loc_name} (match: {match_type})")
            fallback_pmts = meta.get("fallback_payment_types", [])
            if fallback_pmts:
                fr.notes.append(
                    f"⚠ Unrecognized payment type(s) added to Other Sales: "
                    f"{', '.join(fallback_pmts)}"
                )

    # --- Item Reports → category_summary rows ---
    for fname, content in item_files:
        fr = filename_to_fr.get(fname)
        loc_id, loc_name, match_type = _detect_location_for_file(
            content, fname, fallback_location_id
        )
        if loc_id is None:
            err = (
                f"Item Report {fname}: outlet could not be detected from file content. "
                "Make sure the report contains a 'Restaurant Name:' row."
            )
            global_notes.append(err)
            if fr:
                fr.error = err
            continue

        rows, errors, meta = parse_item_report_category_summary(content, fname, loc_id)
        meta["detected_location_id"] = loc_id
        meta["detected_location_name"] = loc_name
        meta["match_type"] = match_type
        meta["file_hash"] = _file_hash(content)
        if fname in file_meta:
            file_meta[fname].update(meta)
        else:
            file_meta[fname] = meta

        if errors:
            for e in errors:
                global_notes.append(e)
            if fr:
                fr.error = "; ".join(errors)
            continue

        cat_by_loc[loc_id].extend(rows)
        for date_str, services in (meta.get("service_sales_by_date") or {}).items():
            item_service_by_loc[loc_id][date_str] = services
        if fr:
            fr.notes.append(
                f"Parsed {len(rows)} category row(s) → {loc_name} (match: {match_type})"
            )

    # --- Complimentary Orders Summary → merge into daily rows ---
    for fname, content in comp_files or []:
        fr = filename_to_fr.get(fname)
        loc_id, loc_name, match_type = _detect_location_for_file(
            content, fname, fallback_location_id
        )
        if loc_id is None:
            err = (
                f"Comp Summary {fname}: outlet could not be detected from file content. "
                "Make sure the report contains a 'Restaurant Name:' row."
            )
            global_notes.append(err)
            if fr:
                fr.error = err
            continue

        rows, errors, meta = parse_order_comp_summary(content, fname, loc_id)
        meta["detected_location_id"] = loc_id
        meta["detected_location_name"] = loc_name
        meta["match_type"] = match_type
        meta["file_hash"] = _file_hash(content)
        if fname in file_meta:
            file_meta[fname].update(meta)
        else:
            file_meta[fname] = meta

        if errors:
            for e in errors:
                global_notes.append(e)
            if fr:
                fr.error = "; ".join(errors)
            continue

        # Merge comp amounts into the daily_by_loc rows for the same location+date.
        # If a Growth Report was uploaded for the same date the comp amount enriches
        # that row; otherwise a standalone daily row is created so the comp data
        # still reaches the database.
        existing_dates: Dict[str, Dict[str, Any]] = {}
        for d_row in daily_by_loc.get(loc_id, []):
            existing_dates[d_row["date"]] = d_row

        for comp_row in rows:
            d = comp_row["date"]
            if d in existing_dates:
                # Merge: add comp amount to existing Growth Report daily row
                existing_dates[d]["complementary_amount"] = round(
                    float(existing_dates[d].get("complementary_amount", 0) or 0)
                    + float(comp_row.get("complementary_amount", 0) or 0),
                    2,
                )
            else:
                # No Growth Report for this date — create a standalone row
                standalone = {
                    "date": d,
                    "location_id": loc_id,
                    "complementary_amount": round(
                        float(comp_row.get("complementary_amount", 0) or 0), 2
                    ),
                    "file_type": "order_comp_summary",
                    "source_report": "order_comp_summary",
                }
                daily_by_loc[loc_id].append(standalone)

        if fr:
            total_comp = round(sum(float(r.get("complementary_amount", 0) or 0) for r in rows), 2)
            fr.notes.append(
                f"Parsed {len(rows)} comp day(s) totalling ₹{total_comp:,.2f} → "
                f"{loc_name} (match: {match_type})"
            )

    return dict(daily_by_loc), dict(cat_by_loc), file_meta, dict(item_service_by_loc)


def _build_location_results_from_daily(
    daily_by_loc: Dict[int, List[Dict[str, Any]]],
) -> Dict[int, List[DayResult]]:
    """Wrap daily rows as DayResult objects, one per (location, date)."""
    location_results: Dict[int, List[DayResult]] = {}
    for loc_id, rows in daily_by_loc.items():
        by_date: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for r in rows:
            by_date[r["date"]].append(r)
        day_results: List[DayResult] = []
        for date_str, date_rows in sorted(by_date.items()):
            # If multiple rows for same date (shouldn't happen normally), merge
            merged = date_rows[0].copy()
            for extra in date_rows[1:]:
                for k, v in extra.items():
                    if isinstance(v, (int, float)) and isinstance(merged.get(k), (int, float)):
                        merged[k] = merged[k] + v
            day_results.append(
                DayResult(
                    date=date_str,
                    merged=merged,
                    source_kinds=["growth_report_day_wise"],
                )
            )
        location_results[loc_id] = day_results
    return location_results


def _check_completeness(
    daily_by_loc: Dict[int, List[Dict[str, Any]]],
    cat_by_loc: Dict[int, List[Dict[str, Any]]],
    global_notes: List[str],
) -> None:
    """Warn (not block) when one report type is missing for an outlet."""
    all_locs = set(daily_by_loc.keys()) | set(cat_by_loc.keys())
    for loc_id in all_locs:
        has_daily = bool(daily_by_loc.get(loc_id))
        has_cat = bool(cat_by_loc.get(loc_id))
        if has_daily and not has_cat:
            global_notes.append(
                f"⚠️ Outlet {loc_id}: Growth Report uploaded but Item Report missing. "
                "Category summary will not be saved for these dates."
            )
        elif has_cat and not has_daily:
            global_notes.append(
                f"ℹ️ Outlet {loc_id}: Item Report uploaded without Growth Report. "
                "Category summary will be saved; daily financial summary skipped."
            )


# ---------------------------------------------------------------------------
# Main orchestration
# ---------------------------------------------------------------------------


def process_smart_upload(
    files: List[Tuple[str, bytes]],
    location_id: int,
) -> SmartUploadResult:
    """Classify all uploaded files, parse the importable ones, merge by date.

    Args:
        files:        List of (filename, raw_bytes) tuples.
        location_id:  Fallback DB location ID if outlet detection fails.

    Returns:
        SmartUploadResult with per-file results, per-location day results,
        per-location category results, and parse/save notes.
    """
    _t0 = time.monotonic()

    file_results: List[FileResult] = []
    global_notes: List[str] = []

    # Step 1 — classify every file
    classified: Dict[str, List[Tuple[str, bytes]]] = defaultdict(list)
    for fname, content in files:
        kind, label = file_detector.detect_and_describe(content, fname)
        importable = file_detector.is_importable(kind)
        logger.info("File detected: name=%s type=%s importable=%s", fname, kind, importable)
        fr = FileResult(
            filename=fname,
            kind=kind,
            kind_label=label,
            importable=importable,
            content=content,
        )
        file_results.append(fr)
        if file_detector.is_skippable(kind):
            fr.notes.append(f"Skipped — {label} does not add new data.")
        else:
            classified[kind].append((fname, content))

    filename_to_fr: Dict[str, FileResult] = {fr.filename: fr for fr in file_results}

    # Step 2 — NEW FLOW: Growth Report + Item Report + Comp Summary
    #          (auto-detects outlet from content)
    growth_files = classified.get("growth_report_day_wise", [])
    item_files_new = classified.get("item_order_details", [])
    comp_files = classified.get("order_comp_summary", [])

    daily_by_loc, cat_by_loc, new_flow_meta, item_service_by_loc = _process_new_flow_files(
        growth_files=growth_files,
        item_files=item_files_new,
        fallback_location_id=location_id,
        filename_to_fr=filename_to_fr,
        global_notes=global_notes,
        comp_files=comp_files,
    )

    _check_completeness(daily_by_loc, cat_by_loc, global_notes)

    # Build location_results from growth report daily rows
    location_results = _build_location_results_from_daily(daily_by_loc)

    # Attach category rows to each DayResult's merged dict so the save path
    # can access them. Category rows are keyed by (loc_id, date, category_name).
    for loc_id_key, cat_rows in cat_by_loc.items():
        if loc_id_key not in location_results:
            # Item report without growth report → create skeleton DayResult entries
            day_results_placeholder: Dict[str, DayResult] = {}
            for cat_row in cat_rows:
                d = cat_row["date"]
                if d not in day_results_placeholder:
                    day_results_placeholder[d] = DayResult(
                        date=d,
                        merged={
                            "date": d,
                            "location_id": loc_id_key,
                            "services": item_service_by_loc.get(loc_id_key, {}).get(d, []),
                        },
                        source_kinds=["item_order_details"],
                    )
                day_results_placeholder[d].merged.setdefault("categories_new", []).append(cat_row)
            location_results.setdefault(loc_id_key, [])
            location_results[loc_id_key].extend(day_results_placeholder.values())
        else:
            # Index category rows by date for fast lookup
            cat_by_date: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
            for cat_row in cat_rows:
                cat_by_date[cat_row["date"]].append(cat_row)
            for day_result in location_results[loc_id_key]:
                day_result.merged["categories_new"] = cat_by_date.get(day_result.date, [])

    # Step 3 — LEGACY FLOW: timing, order_summary, flash, dynamic report
    # (runs alongside new flow; data does not mix)
    timing_services: List[Dict[str, Any]] = []
    for fname, content in classified.get("timing_report", []):
        fr_match = filename_to_fr.get(fname)
        try:
            result = timing_parser.parse_timing_report(content, fname)
            if result and result.get("services"):
                timing_services.append(result)
        except _PARSE_EXCEPTIONS as ex:
            logger.exception("Failed parsing timing_report file=%s", fname)
            if fr_match:
                fr_match.error = str(ex)

    legacy_fragments: List[Dict[str, Any]] = []
    dynamic_dates: set = set()

    for fname, content in classified.get("dynamic_report", []):
        fr_match = filename_to_fr.get(fname)
        try:
            parsed, dr_notes = dynamic_report_parser.parse_dynamic_report(content, fname)
            for n in dr_notes:
                global_notes.append(n)
            if parsed:
                legacy_fragments.extend(parsed)
                dynamic_dates = {f["date"] for f in parsed}
                if fr_match:
                    fr_match.notes.append(
                        f"Parsed {len(parsed)} day(s) from Dynamic Report (legacy flow)."
                    )
        except _PARSE_EXCEPTIONS as ex:
            logger.exception("Failed parsing dynamic_report file=%s", fname)
            if fr_match:
                fr_match.error = str(ex)

    for fname, content in classified.get("order_summary_csv", []):
        fr_match = filename_to_fr.get(fname)
        try:
            parsed, notes_csv = parse_order_summary_csv(content, fname)
            for n in notes_csv:
                global_notes.append(n)
            if parsed:
                for p in parsed:
                    if p["date"] not in dynamic_dates:
                        legacy_fragments.append(p)
        except _PARSE_EXCEPTIONS as ex:
            logger.exception("Failed parsing order_summary_csv file=%s", fname)
            if fr_match:
                fr_match.error = str(ex)

    item_dates_legacy: set = set()
    # Legacy item_order_details path: only used when no growth report was parsed
    # for the same location (to avoid double-counting)
    if not growth_files:
        for fname, content in classified.get("item_order_details", []):
            fr_match = filename_to_fr.get(fname)
            try:
                parsed = pos_parser.parse_item_order_details(content, fname)
                if parsed:
                    for p in parsed:
                        if p["date"] not in dynamic_dates:
                            legacy_fragments.append(p)
                            item_dates_legacy.add(p["date"])
                    if fr_match:
                        fr_match.notes.append(
                            f"Parsed {len(parsed)} day(s) via legacy Item Report parser."
                        )
            except _PARSE_EXCEPTIONS as ex:
                logger.exception("Failed parsing item_order_details file=%s", fname)
                if fr_match:
                    fr_match.error = str(ex)

    for fname, content in classified.get("flash_report", []):
        fr_match = filename_to_fr.get(fname)
        try:
            parsed, notes_fl = parse_flash_report(content, fname)
            for n in notes_fl:
                global_notes.append(n)
            if parsed:
                for p in parsed:
                    if p["date"] not in item_dates_legacy and p["date"] not in dynamic_dates:
                        legacy_fragments.append(p)
        except _PARSE_EXCEPTIONS as ex:
            logger.exception("Failed parsing flash_report file=%s", fname)
            if fr_match:
                fr_match.error = str(ex)

    # Route legacy fragments to location_results
    if legacy_fragments:
        all_locations = database.get_all_locations()
        restaurant_to_loc = build_restaurant_location_map(all_locations, config.RESTAURANT_NAME_MAP)
        tagged_fragments, untagged_fragments = group_fragments_by_restaurant(legacy_fragments)
        routed_fragments = route_tagged_fragments_by_location(
            tagged_by_restaurant=tagged_fragments,
            restaurant_to_location=restaurant_to_loc,
            global_notes=global_notes,
        )
        for loc_id_legacy, loc_frags in routed_fragments.items():
            # Only add legacy days that are NOT already covered by new flow
            new_flow_dates = {dr.date for dr in location_results.get(loc_id_legacy, [])}
            legacy_days = merge_fragments_by_date(loc_frags, timing_services)
            for day_result in legacy_days:
                if day_result.date not in new_flow_dates:
                    location_results.setdefault(loc_id_legacy, []).append(day_result)

        untagged_days = merge_fragments_by_date(untagged_fragments, timing_services)
        if untagged_days:
            new_flow_dates_fallback = {dr.date for dr in location_results.get(location_id, [])}
            for day_result in untagged_days:
                if day_result.date not in new_flow_dates_fallback:
                    location_results.setdefault(location_id, []).append(day_result)

    # Attach new_flow_meta to file results for upload tab display
    for fname, meta in new_flow_meta.items():
        fr = filename_to_fr.get(fname)
        if fr:
            fr.notes.append(
                f"Period: {meta.get('period_start', '?')} → {meta.get('period_end', '?')}"
            )

    result = SmartUploadResult(
        files=file_results,
        days=[],  # deprecated; use location_results
        global_notes=global_notes,
        location_results=location_results,
    )

    # Attach file_meta to result for use in save step (upload_history + validation)
    result.new_flow_meta = new_flow_meta  # type: ignore[attr-defined]
    result.category_by_loc = cat_by_loc  # type: ignore[attr-defined]
    result.item_service_by_loc = item_service_by_loc  # type: ignore[attr-defined]

    _elapsed = time.monotonic() - _t0
    total_days = sum(len(days) for days in location_results.values())
    logger.info(
        "Upload processing complete: files=%d locations=%d days=%d elapsed=%.2fs",
        len(files),
        len(location_results),
        total_days,
        _elapsed,
    )
    return result


# ---------------------------------------------------------------------------
# Save path
# ---------------------------------------------------------------------------


def save_smart_upload_results(
    result: SmartUploadResult,
    location_id: int,
    uploaded_by: str,
    monthly_target: float = 0.0,
    daily_target: float = 0.0,
    seat_count: Optional[int] = None,
) -> Tuple[int, int, List[str]]:
    """Save parsed upload data to the database.

    New flow: growth report rows → daily_summary; item report rows → category_summary.
    Legacy flow: dynamic report / item report → existing path.

    Returns (saved_count, skipped_count, messages).
    """
    _save_t0 = time.monotonic()

    import database_writes as db_writes
    from database import get_supabase_client, use_supabase

    saved = 0
    skipped = 0
    messages: List[str] = []

    if not result.location_results:
        return 0, 0, ["No parsed data to save"]

    is_supabase = use_supabase()
    client = get_supabase_client() if is_supabase else None
    if is_supabase and client is None:
        return 0, 0, ["Could not connect to Supabase"]

    new_flow_meta: Dict[str, Any] = getattr(result, "new_flow_meta", {})
    cat_by_loc: Dict[int, List[Dict[str, Any]]] = getattr(result, "category_by_loc", {})
    item_service_by_loc: Dict[int, Dict[str, List[Dict[str, Any]]]] = getattr(
        result, "item_service_by_loc", {}
    )

    daily_rows: List[Dict[str, Any]] = []
    payment_method_rows: List[Dict[str, Any]] = []
    cat_records: List[Dict[str, Any]] = []
    synthetic_bill_items: List[Dict[str, Any]] = []
    upload_batch: List[Dict[str, Any]] = []
    dates_locs: set = set()

    # ── Step 1: Build save payloads from location_results ──
    for loc_id, day_results in result.location_results.items():
        for day_result in day_results:
            if day_result.errors:
                skipped += 1
                for err in day_result.errors:
                    messages.append(f"Skipped {day_result.date}: {err}")
                continue

            merged = day_result.merged
            date_str = str(merged.get("date", day_result.date))
            source_kinds = day_result.source_kinds or []

            # NEW FLOW: growth report → daily_summary
            if "growth_report_day_wise" in source_kinds:
                if is_supabase:
                    daily_rows.append(
                        db_writes.build_daily_summary_row_new_flow(loc_id, date_str, merged)
                    )
                    for payment_method in merged.get("payment_methods") or []:
                        payment_method_rows.append(
                            {
                                "location_id": loc_id,
                                "date": date_str,
                                "payment_method": payment_method["payment_method"],
                                "payment_key": payment_method["payment_key"],
                                "amount": payment_method["amount"],
                                "source_report": "growth_report_day_wise",
                            }
                        )
                    dates_locs.add((date_str, loc_id))
                    item_services = item_service_by_loc.get(loc_id, {}).get(date_str, [])
                    if item_services:
                        synthetic_bill_items.extend(
                            _build_item_report_bill_items_from_services(
                                loc_id, date_str, {"services": item_services}
                            )
                        )
                    saved += 1

                    # Build upload history row for this day
                    source_fn = _find_source_filename(result, "growth_report_day_wise")
                    fmeta = _find_file_meta(new_flow_meta, loc_id)
                    upload_batch.append(
                        _build_upload_history_row(
                            loc_id=loc_id,
                            date_str=date_str,
                            filename=source_fn or "unknown",
                            file_type="growth_report_day_wise",
                            uploaded_by=uploaded_by,
                            fmeta=fmeta,
                        )
                    )
                else:
                    # SQLite fallback (no new fields — best effort)
                    try:
                        database.save_daily_summary(loc_id, merged)
                        saved += 1
                    except _PARSE_EXCEPTIONS as ex:
                        messages.append(f"⚠️ Could not save {date_str} for outlet {loc_id}: {ex}")
                        skipped += 1
                continue

            # LEGACY FLOW: dynamic report / item report
            if is_supabase:
                has_dynamic = "dynamic_report" in source_kinds
                has_item_report = "item_order_details" in source_kinds
                if not has_dynamic and not has_item_report:
                    skipped += 1
                    messages.append(
                        f"No Dynamic Report for {date_str} — legacy Supabase save "
                        "requires Dynamic Report CSV data."
                    )
                    continue

                daily_rows.append(_build_legacy_daily_row(loc_id, date_str, merged))
                for cat in merged.get("categories") or []:
                    cat_name = str(cat.get("category", "") or "").strip()
                    if not cat_name:
                        continue
                    cat_records.append(
                        {
                            "location_id": loc_id,
                            "date": date_str,
                            "category_name": cat_name,
                            "normalized_category": cat_name,
                            "net_amount": round(float(cat.get("amount", 0) or 0), 2),
                            "qty": int(cat.get("qty", 0) or 0),
                            "source_report": "dynamic_report",
                        }
                    )
                dates_locs.add((date_str, loc_id))

                if has_item_report and not has_dynamic:
                    synthetic_bill_items.extend(
                        _build_item_report_bill_items_from_services(loc_id, date_str, merged)
                    )

                source_fn = _find_source_filename(result, "dynamic_report")
                if not source_fn and has_item_report:
                    source_fn = _find_source_filename(result, "item_order_details")
                upload_batch.append(
                    _build_upload_history_row(
                        loc_id=loc_id,
                        date_str=date_str,
                        filename=source_fn or "unknown",
                        file_type="dynamic_report",
                        uploaded_by=uploaded_by,
                        fmeta={},
                    )
                )
                saved += 1
            else:
                try:
                    database.save_daily_summary(loc_id, merged)
                    saved += 1
                except _PARSE_EXCEPTIONS as ex:
                    messages.append(f"⚠️ Could not save {date_str} for outlet {loc_id}: {ex}")
                    skipped += 1

    # ── Step 2: Category rows from Item Report (new flow) ──
    # Collect rich category rows from all locations
    for loc_id_key, c_rows in cat_by_loc.items():
        for c in c_rows:
            cat_records.append(c)
            dates_locs.add((c["date"], loc_id_key))

    # ── Step 3: Supabase batch upserts ──
    if is_supabase and client:
        if daily_rows:
            try:
                db_writes.upsert_daily_summaries_supabase_batch(client, daily_rows)
                messages.append(f"Saved {len(daily_rows)} daily summary row(s)")
            except (ValueError, TypeError, KeyError, RuntimeError) as ex:
                logger.exception("Supabase daily_summary upsert failed uploaded_by=%s", uploaded_by)
                messages.append(f"⚠️ Error saving daily summaries: {ex}")

        if cat_records:
            try:
                db_writes.delete_category_summary_batch(client, dates_locs)
            except (ValueError, TypeError, KeyError, RuntimeError) as ex:
                logger.warning("Category pre-delete skipped pairs=%d error=%s", len(dates_locs), ex)
                messages.append("⚠️ Could not clear previous category rows; continuing with upsert.")
            try:
                db_writes.save_category_summary_batch(client, cat_records)
                messages.append(f"Saved {len(cat_records)} category summary record(s)")
            except (ValueError, TypeError, KeyError, RuntimeError) as ex:
                logger.exception("Category save failed uploaded_by=%s", uploaded_by)
                messages.append(f"⚠️ Error saving category summaries: {ex}")

        if payment_method_rows:
            try:
                db_writes.delete_payment_method_sales_batch(client, dates_locs)
                db_writes.save_payment_method_sales_batch(client, payment_method_rows)
                messages.append(f"Saved {len(payment_method_rows)} payment method record(s)")
            except (ValueError, TypeError, KeyError, RuntimeError) as ex:
                logger.exception("Payment method save failed uploaded_by=%s", uploaded_by)
                messages.append(f"⚠️ Error saving payment method records: {ex}")

    # ── Step 4: Raw bill_items from Dynamic Report CSVs (Supabase only, legacy) ──
    if is_supabase and client:
        dynamic_files = [
            fr for fr in result.files if fr.kind == "dynamic_report" and fr.content and not fr.error
        ]
        all_locations = database.get_all_locations() if dynamic_files else []
        for fr in dynamic_files:
            try:
                raw_records, parse_notes = dynamic_report_parser.parse_dynamic_report_raw(
                    fr.content, fr.filename
                )
                for note in parse_notes:
                    messages.append(note)
                if not raw_records:
                    continue
                file_dates_locs: set = set()
                for rec in raw_records:
                    rname = (str(rec.get("restaurant") or "")).strip() or "Boteco"
                    loc = resolve_location_id(
                        restaurant_name=rname,
                        locations=all_locations,
                        aliases=config.RESTAURANT_NAME_MAP,
                        fallback_location_id=1,
                    )
                    file_dates_locs.add((rec.get("bill_date", ""), loc))
                try:
                    db_writes.delete_bill_items_by_dates_locs(client, file_dates_locs)
                except (ValueError, TypeError, KeyError, RuntimeError):
                    messages.append(
                        f"⚠️ Could not clear old bill items before saving {fr.filename}."
                    )
                db_writes.save_bill_items(client, raw_records)
                messages.append(f"Saved {len(raw_records)} bill items from {fr.filename}")
            except (ValueError, TypeError, KeyError, RuntimeError) as ex:
                messages.append(f"⚠️ Error saving bill items from {fr.filename}: {ex}")

        if synthetic_bill_items:
            try:
                db_writes.delete_bill_items_by_dates_locs(client, dates_locs)
            except (ValueError, TypeError, KeyError, RuntimeError):
                messages.append(
                    "⚠️ Could not clear old bill items before saving Item Report service data."
                )
            try:
                db_writes.save_bill_items(client, synthetic_bill_items)
                messages.append(
                    "Saved "
                    f"{len(synthetic_bill_items)} bill items from Item Report timestamp buckets"
                )
            except (ValueError, TypeError, KeyError, RuntimeError) as ex:
                messages.append(f"⚠️ Error saving Item Report service bill items: {ex}")

    # ── Step 5: Upload history ──
    if upload_batch:
        try:
            db_writes.save_upload_records_batch(upload_batch)
        except (ValueError, TypeError, KeyError, RuntimeError) as ex:
            logger.exception("Upload history save failed uploaded_by=%s", uploaded_by)
            messages.append(f"⚠️ Error saving upload history: {ex}")

    messages.append(f"Processed {saved} day/location row(s), {skipped} skipped")
    _elapsed = time.monotonic() - _save_t0
    logger.info("Upload save complete: days_saved=%d elapsed=%.2fs", saved, _elapsed)
    return saved, skipped, messages


# ---------------------------------------------------------------------------
# Private helpers for save path
# ---------------------------------------------------------------------------


def _find_source_filename(result: SmartUploadResult, kind: str) -> Optional[str]:
    for fr in result.files:
        if fr.kind == kind and fr.importable and not fr.error:
            return fr.filename
    return None


def _find_file_meta(new_flow_meta: Dict[str, Any], loc_id: int) -> Dict[str, Any]:
    """Find the first file-meta entry matching a location_id."""
    for meta in new_flow_meta.values():
        if meta.get("detected_location_id") == loc_id:
            return meta
    return {}


def _build_upload_history_row(
    loc_id: int,
    date_str: str,
    filename: str,
    file_type: str,
    uploaded_by: str,
    fmeta: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "location_id": loc_id,
        "date": date_str,
        "filename": filename,
        "file_type": file_type,
        "uploaded_by": uploaded_by,
        "detected_location_name": fmeta.get("detected_location_name"),
        "detected_report_type": file_type,
        "period_start": fmeta.get("period_start"),
        "period_end": fmeta.get("period_end"),
        "row_count": fmeta.get("row_count"),
        "status": "imported",
        "file_hash": fmeta.get("file_hash"),
    }


def _build_item_report_bill_items_from_services(
    location_id: int, date_str: str, merged: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """Build synthetic bill_items rows from Item Report service buckets.

    Service Sales analytics in Supabase reads `bill_items.created_date_time`. For
    Item Report-only legacy uploads we synthesize one bill_items row per service
    bucket so Lunch/Dinner can be derived from timestamp hour.
    """
    from database_writes import LOCATION_ID_TO_RESTAURANT

    restaurant = LOCATION_ID_TO_RESTAURANT.get(int(location_id), "Boteco")
    hour_by_service = {
        "breakfast": "09:00:00",
        "lunch": "13:00:00",
        "dinner": "20:00:00",
    }
    records: List[Dict[str, Any]] = []

    for svc in merged.get("services") or []:
        service_name = str(svc.get("type", "") or "").strip().lower()
        if service_name not in hour_by_service:
            continue
        amount = float(svc.get("amount", 0) or 0)
        if amount <= 0:
            continue
        created_date_time = f"{date_str} {hour_by_service[service_name]}"
        records.append(
            {
                "restaurant": restaurant,
                "bill_date": date_str,
                "bill_no": f"ITEM-{service_name[:1].upper()}-{date_str}",
                "server_name": None,
                "table_no": None,
                "bill_status": "Success Order",
                "payment_type": None,
                "category_name": "Service Split",
                "item_name": f"{service_name.title()} Bucket",
                "discount_reason": None,
                "created_date_time": created_date_time,
                "item_qty": 1,
                "pax": 0,
                "net_amount": round(amount, 2),
                "gross_amount": round(amount, 2),
                "discount": 0.0,
                "cgst": 0.0,
                "sgst": 0.0,
                "service_charge": 0.0,
                "gst_on_service_charge": 0.0,
                "cancelled_amount": 0.0,
                "complementary_amount": 0.0,
            }
        )

    return records


def _build_legacy_daily_row(loc_id: int, date_str: str, merged: Dict[str, Any]) -> Dict[str, Any]:
    """Build a daily_summary payload from a legacy (dynamic_report) merged dict."""
    return {
        "location_id": loc_id,
        "date": date_str,
        "gross_total": round(float(merged.get("gross_total", 0) or 0), 2),
        "net_total": round(float(merged.get("net_total", 0) or 0), 2),
        "covers": int(merged.get("covers", 0) or 0),
        "discount": round(float(merged.get("discount", 0) or 0), 2),
        "cgst": round(float(merged.get("cgst", 0) or 0), 2),
        "sgst": round(float(merged.get("sgst", 0) or 0), 2),
        "service_charge": round(float(merged.get("service_charge", 0) or 0), 2),
        "gst_on_service_charge": 0,
        "cancelled_amount": 0,
        "complementary_amount": round(float(merged.get("complimentary", 0) or 0), 2),
        "cash_sales": round(float(merged.get("cash_sales", 0) or 0), 2),
        "card_sales": round(float(merged.get("card_sales", 0) or 0), 2),
        "gpay_sales": round(float(merged.get("gpay_sales", 0) or 0), 2),
        "zomato_sales": round(float(merged.get("zomato_sales", 0) or 0), 2),
        "other_sales": round(float(merged.get("other_sales", 0) or 0), 2),
        "order_count": int(merged.get("order_count", 0) or 0),
        "source_report": "dynamic_report",
    }
