"""
Smart upload: accept any mix of Petpooja exports, auto-detect each file type,
route to the right parser, merge data by date, and return save-ready records.

Supports:
  dynamic_report       - Dynamic Report CSV (per-bill order-level)        [PRIMARY]
  item_order_details   - Item Report With Customer/Order Details (.xlsx)  [FALLBACK]
  timing_report        - Restaurant Timing Report (.xlsx)                 [SERVICE BREAKDOWN]
  order_summary_csv    - Order Summary Report (.csv)                      [BACKUP]
  flash_report         - POS Collection / Flash Report (.xlsx)            [CROSS-CHECK]
  group_wise           - Item Report Group Wise (.xlsx)                   [SKIP]
  all_restaurant       - All Restaurant Sales Report (.xlsx)              [SKIP]
  comparison           - Restaurant Wise Comparison (.xls)                [SKIP]
  unknown              - Unrecognised                                      [SKIP]
"""

from __future__ import annotations

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
from uploads.models import DayResult, FileResult, SmartUploadResult
from uploads.parsers.flash_report import parse_flash_report
from uploads.parsers.order_summary import parse_order_summary_csv

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


_FILE_TYPE_PREFERENCE = (
    "dynamic_report",
    "item_order_details",
    "order_summary_csv",
    "flash_report",
)


def _primary_file_type(source_kinds: List[str]) -> str:
    for kind in _FILE_TYPE_PREFERENCE:
        if kind in source_kinds:
            return kind
    return "item_order_details"


# ---------------------------------------------------------------------------
# Internal parsers for non-Item-Report types
# ---------------------------------------------------------------------------


def _parse_order_summary_csv(
    content: bytes, filename: str
) -> Tuple[Optional[List[Dict[str, Any]]], List[str]]:
    """Compatibility wrapper around extracted Order Summary parser."""
    return parse_order_summary_csv(content, filename)


def _parse_flash_report(
    content: bytes, filename: str
) -> Tuple[Optional[List[Dict[str, Any]]], List[str]]:
    """Compatibility wrapper around extracted Flash Report parser."""
    return parse_flash_report(content, filename)


# ---------------------------------------------------------------------------
# Main orchestration
# ---------------------------------------------------------------------------


def process_smart_upload(
    files: List[Tuple[str, bytes]],
    location_id: int,
) -> SmartUploadResult:
    """
    Classify all uploaded files, parse the importable ones, merge by date.

    Args:
        files:        List of (filename, raw_bytes) tuples.
        location_id:  Target DB location ID (used for overlap detection later).

    Returns:
        SmartUploadResult with per-file results, per-day results, and
        parse/save notes for the upload batch.
    """
    import time

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

    # Step 2 — collect timing report services (date may be None; matched later)
    timing_services: List[Dict[str, Any]] = []
    for fname, content in classified.get("timing_report", []):
        fr_match = filename_to_fr.get(fname)
        try:
            result = timing_parser.parse_timing_report(content, fname)
            if result and result.get("services"):
                timing_services.append(result)
            elif result is None:
                note = f"Timing Report {fname}: could not extract service breakdown."
                global_notes.append(note)
                if fr_match:
                    fr_match.notes.append(note)
        except _PARSE_EXCEPTIONS as ex:
            logger.exception("Failed parsing timing_report file=%s", fname)
            note = f"Error parsing Timing Report {fname}: {ex}"
            global_notes.append(note)
            if fr_match:
                fr_match.error = str(ex)

    # Step 4 — parse primary data sources in priority order
    fragments: List[Dict[str, Any]] = []

    # 4a. Dynamic Report CSV (primary — per-bill order-level data)
    dynamic_dates: set = set()
    for fname, content in classified.get("dynamic_report", []):
        fr_match = filename_to_fr.get(fname)
        try:
            parsed, dr_notes = dynamic_report_parser.parse_dynamic_report(content, fname)
            for n in dr_notes:
                global_notes.append(n)
            if parsed:
                fragments.extend(parsed)
                dynamic_dates = {f["date"] for f in parsed}
                if fr_match:
                    fr_match.notes.append(f"Parsed {len(parsed)} day(s) from Dynamic Report.")
            else:
                note = f"Dynamic Report {fname}: no data rows found."
                global_notes.append(note)
                if fr_match:
                    fr_match.error = note
        except _PARSE_EXCEPTIONS as ex:
            logger.exception("Failed parsing dynamic_report file=%s", fname)
            note = f"Error parsing Dynamic Report {fname}: {ex}"
            global_notes.append(note)
            if fr_match:
                fr_match.error = str(ex)

    # 4b. Item Report (fallback — only for dates not covered by Dynamic Report)
    for fname, content in classified.get("item_order_details", []):
        fr_match = filename_to_fr.get(fname)
        try:
            parsed = pos_parser.parse_item_order_details(content, fname)
            if parsed:
                new_days = 0
                for p in parsed:
                    if p["date"] not in dynamic_dates:
                        fragments.append(p)
                        new_days += 1
                    else:
                        if fr_match:
                            fr_match.notes.append(
                                f"Date {p['date']} already covered by Dynamic Report — skipped."
                            )
                if fr_match:
                    if new_days > 0:
                        fr_match.notes.append(f"Added {new_days} day(s) not in Dynamic Report.")
                    elif dynamic_dates:
                        fr_match.notes.append("All dates already covered by Dynamic Report.")
                    else:
                        fr_match.notes.append(f"Parsed {len(parsed)} day(s) of sales data.")
            else:
                note = f"Item Report {fname}: no data rows found."
                global_notes.append(note)
                if fr_match:
                    fr_match.error = note
        except _PARSE_EXCEPTIONS as ex:
            logger.exception("Failed parsing item_order_details file=%s", fname)
            note = f"Error parsing Item Report {fname}: {ex}"
            global_notes.append(note)
            if fr_match:
                fr_match.error = str(ex)

    item_dates = {f["date"] for f in fragments if f.get("file_type") == "item_order_details"}

    # 4c. Order Summary CSV (backup — only for dates not covered by Item Report)
    for fname, content in classified.get("order_summary_csv", []):
        fr_match = filename_to_fr.get(fname)
        try:
            parsed, notes_csv = _parse_order_summary_csv(content, fname)
            for n in notes_csv:
                global_notes.append(n)
            if parsed:
                new_days = 0
                for p in parsed:
                    if p["date"] not in item_dates:
                        fragments.append(p)
                        new_days += 1
                    else:
                        if fr_match:
                            fr_match.notes.append(
                                f"Date {p['date']} already covered by Item Report — skipped."
                            )
                if fr_match and new_days > 0:
                    fr_match.notes.append(f"Added {new_days} day(s) not in Item Report.")
        except _PARSE_EXCEPTIONS as ex:
            logger.exception("Failed parsing order_summary_csv file=%s", fname)
            note = f"Error parsing Order Summary {fname}: {ex}"
            global_notes.append(note)
            if fr_match:
                fr_match.error = str(ex)

    # 4c. Flash Report (supplement: fills service_charge gap on Item Report days)
    for fname, content in classified.get("flash_report", []):
        fr_match = filename_to_fr.get(fname)
        try:
            parsed, notes_fl = _parse_flash_report(content, fname)
            for n in notes_fl:
                global_notes.append(n)
            if parsed:
                for p in parsed:
                    if p["date"] not in item_dates:
                        fragments.append(p)
                    else:
                        # Supplement service_charge if Item Report didn't have it
                        if p.get("service_charge"):
                            for frag in fragments:
                                if (
                                    frag.get("date") == p["date"]
                                    and frag.get("file_type") == "item_order_details"
                                    and not frag.get("service_charge")
                                ):
                                    frag["service_charge"] = p["service_charge"]
                                    if fr_match:
                                        fr_match.notes.append(
                                            f"Supplemented service_charge for {p['date']} from Flash Report."
                                        )
                                    break
        except _PARSE_EXCEPTIONS as ex:
            logger.exception("Failed parsing flash_report file=%s", fname)
            note = f"Error parsing Flash Report {fname}: {ex}"
            global_notes.append(note)
            if fr_match:
                fr_match.error = str(ex)

    # Step 5 — group fragments by restaurant → location, then by date and merge
    from collections import defaultdict as _defaultdict

    # Map restaurant names in CSV → DB location name → location ID
    _restaurant_to_loc: Dict[str, int] = {}
    _all_locs = database.get_all_locations()
    _name_to_id = {str(loc["name"]): int(loc["id"]) for loc in _all_locs}
    for csv_name, db_name in config.RESTAURANT_NAME_MAP.items():
        if db_name in _name_to_id:
            _restaurant_to_loc[csv_name] = _name_to_id[db_name]

    # Split fragments by restaurant (for dynamic_report) vs untagged (other types)
    by_restaurant: Dict[Optional[str], List[Dict[str, Any]]] = _defaultdict(list)
    for frag in fragments:
        rest = frag.get("restaurant")
        by_restaurant[rest].append(frag)

    # Untagged fragments (item_order_details, etc.) go under None
    # and will be routed to the first location (if any) or kept standalone.
    untagged = by_restaurant.pop(None, [])

    _KIND_PRIORITY = {
        "dynamic_report": 5,
        "item_order_details": 10,
        "order_summary_csv": 20,
        "flash_report": 30,
    }

    location_results: Dict[int, List[DayResult]] = {}

    for rest_name, rest_frags in by_restaurant.items():
        loc_id = _restaurant_to_loc.get(rest_name)
        if loc_id is None:
            global_notes.append(f"Unknown restaurant '{rest_name}' in CSV — skipped.")
            continue

        by_date = pos_parser.group_fragments_by_date(rest_frags)
        day_results: List[DayResult] = []

        for d in sorted(by_date.keys()):
            frags = by_date[d]
            frags.sort(key=lambda f: _KIND_PRIORITY.get(f.get("file_type", ""), 100))
            source_kinds = sorted(
                {
                    str(f.get("file_type"))
                    for f in frags
                    if isinstance(f.get("file_type"), str) and f.get("file_type")
                },
                key=lambda k: _KIND_PRIORITY.get(k, 100),
            )
            merged = pos_parser.merge_upload_fragments(frags)

            # Attach timing services if none already present
            if timing_services and not merged.get("services"):
                matched_timing = next(
                    (t for t in timing_services if t.get("date") == d),
                    timing_services[0] if len(timing_services) == 1 else None,
                )
                if matched_timing and matched_timing.get("services"):
                    merged["services"] = [
                        {"type": s["type"], "amount": s["amount"]}
                        for s in matched_timing["services"]
                    ]

            # Basic validation / coercion (log when we fill in missing values)
            if not merged.get("net_total") and merged.get("gross_total"):
                logger.warning(
                    "net_total missing for %s — defaulting to gross_total (\u20b9%s)",
                    d,
                    merged["gross_total"],
                )
                merged["net_total"] = float(merged["gross_total"])
            if not merged.get("gross_total") and merged.get("net_total"):
                logger.warning(
                    "gross_total missing for %s — defaulting to net_total (\u20b9%s)",
                    d,
                    merged["net_total"],
                )
                merged["gross_total"] = float(merged["net_total"])

            ok, verr, vwarn = pos_parser.validate_data(merged)
            if vwarn:
                logger.warning("Validation warnings for %s: %s", d, "; ".join(vwarn))
            day_results.append(
                DayResult(
                    date=d,
                    merged=merged,
                    source_kinds=source_kinds,
                    errors=(verr if not ok else []),
                    warnings=vwarn,
                )
            )

        location_results[loc_id] = day_results

    # Handle untagged fragments (item_order_details, etc. — no restaurant column)
    if untagged:
        by_date = pos_parser.group_fragments_by_date(untagged)
        day_results: List[DayResult] = []

        for d in sorted(by_date.keys()):
            frags = by_date[d]
            frags.sort(key=lambda f: _KIND_PRIORITY.get(f.get("file_type", ""), 100))
            source_kinds = sorted(
                {
                    str(f.get("file_type"))
                    for f in frags
                    if isinstance(f.get("file_type"), str) and f.get("file_type")
                },
                key=lambda k: _KIND_PRIORITY.get(k, 100),
            )
            merged = pos_parser.merge_upload_fragments(frags)

            if timing_services and not merged.get("services"):
                matched_timing = next(
                    (t for t in timing_services if t.get("date") == d),
                    timing_services[0] if len(timing_services) == 1 else None,
                )
                if matched_timing and matched_timing.get("services"):
                    merged["services"] = [
                        {"type": s["type"], "amount": s["amount"]}
                        for s in matched_timing["services"]
                    ]

            if not merged.get("net_total") and merged.get("gross_total"):
                logger.warning(
                    "net_total missing for %s — defaulting to gross_total (\u20b9%s)",
                    d,
                    merged["gross_total"],
                )
                merged["net_total"] = float(merged["gross_total"])
            if not merged.get("gross_total") and merged.get("net_total"):
                logger.warning(
                    "gross_total missing for %s — defaulting to net_total (\u20b9%s)",
                    d,
                    merged["net_total"],
                )
                merged["gross_total"] = float(merged["net_total"])

            ok, verr, vwarn = pos_parser.validate_data(merged)
            if vwarn:
                logger.warning("Validation warnings for %s: %s", d, "; ".join(vwarn))
            day_results.append(
                DayResult(
                    date=d,
                    merged=merged,
                    source_kinds=source_kinds,
                    errors=(verr if not ok else []),
                    warnings=vwarn,
                )
            )

        # Route untagged to the first available location (or fallback to provided location_id)
        fallback_loc = location_id or next(iter(location_results), None)
        if fallback_loc is not None:
            location_results.setdefault(fallback_loc, []).extend(day_results)
        else:
            # No dynamic report and no fallback — use a sentinel key so data isn't lost
            location_results[location_id] = day_results

    result = SmartUploadResult(
        files=file_results,
        days=[],  # deprecated; use location_results
        global_notes=global_notes,
        location_results=location_results,
    )
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


def save_smart_upload_results(
    result: SmartUploadResult,
    location_id: int,
    uploaded_by: str,
    monthly_target: float = 0.0,
    daily_target: float = 0.0,
    seat_count: Optional[int] = None,
) -> Tuple[int, int, List[str]]:
    """Save parsed upload data to the database.

    Uses the already-correct ``location_results`` from ``process_smart_upload``
    for daily_summary and category_summary (these contain properly distributed
    category amounts and filtered financials from ``_parse_v2``).

    Raw bill_items from Dynamic Report CSVs are additionally stored in Supabase
    for granular analytics (line-item queries, service period derivation, etc.).

    Works with both Supabase and SQLite backends.

    Returns (saved_count, skipped_count, messages).
    """
    import time

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

    # ── Step 1: Save daily_summary + category_summary from location_results ──
    # These come from process_smart_upload → _parse_v2 which correctly:
    #   - distributes bill_net across items by amount/qty ratio
    #   - filters out cancelled/non-SuccessOrder bills
    #   - separates complimentary bills
    #   - buckets payments by Payment Type

    daily_rows: List[Dict[str, Any]] = []
    cat_records: List[Dict[str, Any]] = []
    upload_batch: List[Dict[str, Any]] = []
    dates_locs: set = set()

    for loc_id, day_results in result.location_results.items():
        for day_result in day_results:
            if day_result.errors:
                skipped += 1
                for err in day_result.errors:
                    messages.append(f"Skipped {day_result.date}: {err}")
                continue

            merged = day_result.merged
            date_str = str(merged.get("date", day_result.date))

            if is_supabase and "dynamic_report" not in (day_result.source_kinds or []):
                skipped += 1
                messages.append(
                    f"No Dynamic Report for {date_str} — Supabase save requires Dynamic Report CSV data."
                )
                continue

            dates_locs.add((date_str, loc_id))

            if is_supabase:
                # Build daily_summary row from correctly-parsed merged data
                daily_rows.append(
                    {
                        "location_id": loc_id,
                        "date": date_str,
                        "gross_total": round(float(merged.get("gross_total", 0) or 0), 2),
                        "net_total": round(float(merged.get("net_total", 0) or 0), 2),
                        "covers": int(merged.get("covers", 0) or 0),
                        "discount": round(float(merged.get("discount", 0) or 0), 2),
                        "cgst": round(float(merged.get("cgst", 0) or 0), 2),
                        "sgst": round(float(merged.get("sgst", 0) or 0), 2),
                        "service_charge": round(float(merged.get("service_charge", 0) or 0), 2),
                        "gst_on_service_charge": 0,  # already folded into cgst/sgst by parser
                        "cancelled_amount": 0,  # cancelled bills excluded by parser
                        "complementary_amount": round(
                            float(merged.get("complimentary", 0) or 0), 2
                        ),
                        "cash_sales": round(float(merged.get("cash_sales", 0) or 0), 2),
                        "card_sales": round(float(merged.get("card_sales", 0) or 0), 2),
                        "gpay_sales": round(float(merged.get("gpay_sales", 0) or 0), 2),
                        "zomato_sales": round(float(merged.get("zomato_sales", 0) or 0), 2),
                        "other_sales": round(float(merged.get("other_sales", 0) or 0), 2),
                        "order_count": int(merged.get("order_count", 0) or 0),
                    }
                )

                # Build category_summary rows from correctly-distributed categories
                for cat in merged.get("categories") or []:
                    cat_name = str(cat.get("category", "") or "").strip()
                    if not cat_name:
                        continue
                    cat_records.append(
                        {
                            "location_id": loc_id,
                            "date": date_str,
                            "category_name": cat_name,
                            "net_amount": round(float(cat.get("amount", 0) or 0), 2),
                            "qty": int(cat.get("qty", 0) or 0),
                        }
                    )
            else:
                # SQLite path: save_daily_summary handles item_sales + service_sales
                try:
                    database.save_daily_summary(loc_id, merged)
                except (ValueError, TypeError, KeyError, RuntimeError, OSError) as ex:
                    logger.exception(
                        "SQLite save failed in smart_upload.py location_id=%s date=%s uploaded_by=%s error=%s",
                        loc_id,
                        date_str,
                        uploaded_by,
                        ex,
                    )
                    messages.append(
                        f"⚠️ Could not save {date_str} for outlet {loc_id} to SQLite: {ex}"
                    )
                    skipped += 1
                    continue

            # Build file-type-specific source info for upload history
            source_kinds = day_result.source_kinds
            primary_kind = source_kinds[0] if source_kinds else "dynamic_report"
            # Find filename that contributed to this day
            source_filename = None
            for fr in result.files:
                if fr.kind == primary_kind and fr.importable:
                    source_filename = fr.filename
                    break
            upload_batch.append(
                {
                    "location_id": loc_id,
                    "date": date_str,
                    "filename": source_filename or "unknown",
                    "file_type": primary_kind,
                    "uploaded_by": uploaded_by,
                }
            )

            saved += 1

    # ── Step 2: Supabase batch upserts ──
    if is_supabase and client:
        if daily_rows:
            try:
                db_writes.upsert_daily_summaries_supabase_batch(client, daily_rows)
                messages.append(f"Saved {len(daily_rows)} daily summary row(s)")
            except (ValueError, TypeError, KeyError, RuntimeError) as ex:
                logger.exception(
                    "Supabase daily_summary upsert failed in smart_upload.py uploaded_by=%s error=%s",
                    uploaded_by,
                    ex,
                )
                messages.append(f"⚠️ Error saving daily summaries: {ex}")

        if cat_records:
            try:
                # Batch-delete existing category_summary for affected dates/locations
                # before upsert to clear stale categories that no longer appear
                try:
                    db_writes.delete_category_summary_batch(client, dates_locs)
                except (ValueError, TypeError, KeyError, RuntimeError) as ex:
                    logger.warning(
                        "Category pre-delete skipped in smart_upload.py uploaded_by=%s pairs=%d error=%s",
                        uploaded_by,
                        len(dates_locs),
                        ex,
                    )
                    messages.append(
                        "⚠️ Could not clear previous category rows before re-save; continuing with upsert."
                    )
                db_writes.save_category_summary_batch(client, cat_records)
                messages.append(f"Saved {len(cat_records)} category summary records")
            except (ValueError, TypeError, KeyError, RuntimeError) as ex:
                logger.exception(
                    "Category save failed in smart_upload.py uploaded_by=%s error=%s",
                    uploaded_by,
                    ex,
                )
                messages.append(f"⚠️ Error saving category summaries: {ex}")

    # ── Step 3: Raw bill_items from Dynamic Report CSVs (Supabase only) ──
    if is_supabase and client:
        dynamic_files = [
            fr for fr in result.files if fr.kind == "dynamic_report" and fr.content and not fr.error
        ]
        for fr in dynamic_files:
            try:
                raw_records, parse_notes = dynamic_report_parser.parse_dynamic_report_raw(
                    fr.content, fr.filename
                )
                for note in parse_notes:
                    messages.append(note)

                if not raw_records:
                    continue

                # Determine which (date, location) pairs are in this file
                file_dates_locs: set = set()
                for rec in raw_records:
                    rname = (str(rec.get("restaurant") or "")).strip() or "Boteco"
                    loc = db_writes._get_location_id(rname)
                    file_dates_locs.add((rec.get("bill_date", ""), loc))

                # Batch-delete existing bill_items for these dates/locations (idempotent re-upload)
                try:
                    db_writes.delete_bill_items_by_dates_locs(client, file_dates_locs)
                except (ValueError, TypeError, KeyError, RuntimeError) as ex:
                    logger.warning(
                        "bill_items pre-delete skipped in smart_upload.py file=%s uploaded_by=%s pairs=%d error=%s",
                        fr.filename,
                        uploaded_by,
                        len(file_dates_locs),
                        ex,
                    )
                    messages.append(
                        f"⚠️ Could not clear old bill items before saving {fr.filename}; new rows will still be inserted."
                    )

                db_writes.save_bill_items(client, raw_records)
                messages.append(f"Saved {len(raw_records)} bill items from {fr.filename}")
            except (ValueError, TypeError, KeyError, RuntimeError) as ex:
                messages.append(f"⚠️ Error saving bill items from {fr.filename}: {ex}")
                logger.exception(
                    "Failed to save bill_items in smart_upload.py file=%s uploaded_by=%s error=%s",
                    fr.filename,
                    uploaded_by,
                    ex,
                )

    # ── Step 4: Upload history ──
    if upload_batch:
        try:
            db_writes.save_upload_records_batch(upload_batch)
        except (ValueError, TypeError, KeyError, RuntimeError) as ex:
            logger.exception(
                "Upload history save failed in smart_upload.py uploaded_by=%s rows=%d error=%s",
                uploaded_by,
                len(upload_batch),
                ex,
            )
            messages.append(f"⚠️ Error saving upload history: {ex}")

    messages.append(f"Processed {saved} day/location row(s), {skipped} skipped")
    _elapsed = time.monotonic() - _save_t0
    logger.info("Upload save complete: days_saved=%d elapsed=%.2fs", saved, _elapsed)
    return saved, skipped, messages
