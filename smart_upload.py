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
from dataclasses import dataclass, field
from io import BytesIO
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

import config
import database
import dynamic_report_parser
import file_detector
import pos_parser
import timing_parser
from boteco_logger import get_logger

logger = get_logger(__name__)

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
# Result types
# ---------------------------------------------------------------------------


@dataclass
class FileResult:
    """Per-file detection and parsing outcome."""

    filename: str
    kind: str
    kind_label: str
    importable: bool
    notes: List[str] = field(default_factory=list)
    error: Optional[str] = None
    content: Optional[bytes] = field(default_factory=None)


@dataclass
class DayResult:
    """Parsed + merged data ready for one calendar date."""

    date: str
    merged: Dict[str, Any]
    source_kinds: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


@dataclass
class SmartUploadResult:
    """Full result returned by process_smart_upload()."""

    files: List[FileResult]
    days: List[DayResult]
    global_notes: List[str] = field(default_factory=list)
    location_results: Dict[int, List[DayResult]] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Internal parsers for non-Item-Report types
# ---------------------------------------------------------------------------


def _parse_order_summary_csv(
    content: bytes, filename: str
) -> Tuple[Optional[List[Dict[str, Any]]], List[str]]:
    """Parse Order Summary CSV (order-level rows) → list of per-day dicts."""
    notes: List[str] = []
    try:
        df = pd.read_csv(BytesIO(content))
    except _PARSE_EXCEPTIONS as ex:
        return None, [f"Could not read CSV: {ex}"]

    df.columns = [c.strip() for c in df.columns]
    col_lower = {c.lower(): c for c in df.columns}

    # Required columns (case-insensitive)
    def _get_col(*names: str) -> Optional[str]:
        for n in names:
            if n in col_lower:
                return col_lower[n]
        return None

    date_col = _get_col("date")
    amount_col = _get_col("my_amount", "amount")
    status_col = _get_col("status")

    if not date_col or not amount_col:
        return None, ["Order Summary CSV missing required columns (date / my_amount)."]

    days: Dict[str, Dict[str, Any]] = {}

    for _, row in df.iterrows():
        date_raw = str(row.get(date_col, ""))[:10]
        day = pos_parser.cell_date_to_iso(date_raw) or pos_parser.parse_date(date_raw)
        if not day:
            continue

        status = (
            str(row.get(status_col, "")).strip().lower() if status_col else "success"
        )
        if "complimentary" in status:
            continue
        if status not in ("success", ""):
            continue

        if day not in days:
            days[day] = {
                "net": 0.0,
                "gross": 0.0,
                "tax": 0.0,
                "cash": 0.0,
                "card": 0.0,
                "gpay": 0.0,
                "zomato": 0.0,
                "other": 0.0,
                "discount": 0.0,
                "service_charge": 0.0,
                "covers": 0,
            }
        b = days[day]
        amt = pos_parser.f(row.get(amount_col))
        b["net"] += amt
        b["gross"] += amt

        pay_col = _get_col("payment_type", "payment type")
        if pay_col:
            bucket = pos_parser.payment_bucket(str(row.get(pay_col, "")))
            if bucket in ("cash", "card", "gpay", "zomato"):
                b[bucket] += amt
            else:
                b["other"] += amt

    out: List[Dict[str, Any]] = []
    for d in sorted(days.keys()):
        b = days[d]
        if b["net"] <= 0:
            continue
        out.append(
            {
                "date": d,
                "filename": filename,
                "file_type": "order_summary_csv",
                "gross_total": b["gross"],
                "net_total": b["net"],
                "cash_sales": b["cash"],
                "card_sales": b["card"],
                "gpay_sales": b["gpay"],
                "zomato_sales": b["zomato"],
                "other_sales": b["other"],
                "discount": b["discount"],
                "complimentary": 0.0,
                "cgst": 0.0,
                "sgst": 0.0,
                "service_charge": b["service_charge"],
                "covers": b["covers"],
                "categories": [],
                "services": [],
            }
        )
    return (out if out else None), notes


def _parse_flash_report(
    content: bytes, filename: str
) -> Tuple[Optional[List[Dict[str, Any]]], List[str]]:
    """
    Parse Flash Report / POS Collection Report.
    This is a single-day summary with category and payment sections.
    """
    notes: List[str] = []
    bio = BytesIO(content)
    df: Optional[pd.DataFrame] = None
    for engine in (None, "openpyxl", "xlrd"):
        try:
            bio.seek(0)
            kw = {"engine": engine} if engine else {}
            df = pd.read_excel(bio, sheet_name=0, header=None, **kw)
            break
        except (ValueError, ImportError, OSError, pd.errors.ParserError):
            continue

    if df is None or df.empty:
        return None, ["Could not read Flash Report."]

    # Find the date
    date_str: Optional[str] = None
    for i in range(min(10, len(df))):
        label = pos_parser.norm_header(df.iloc[i, 0]) if len(df.columns) > 0 else ""
        if "date" in label:
            val = (
                str(df.iloc[i, 1]).strip()
                if len(df.columns) > 1 and pd.notna(df.iloc[i, 1])
                else ""
            )
            if val and val.lower() != "nan":
                date_str = pos_parser.cell_date_to_iso(val) or pos_parser.parse_date(
                    val
                )
        if date_str:
            break

    if not date_str:
        return None, ["Flash Report: could not extract date."]

    # Find the summary header row (contains "orders" and "my amount" or "net sales")
    summary_row: Optional[int] = None
    for i in range(len(df)):
        label = pos_parser.norm_header(df.iloc[i, 0])
        if label == "orders" or (
            "my amount"
            in " ".join(pos_parser.norm_header(v) for v in df.iloc[i].values)
        ):
            summary_row = i
            break

    net = 0.0
    gross = 0.0
    cash = 0.0
    cgst = 0.0
    sgst = 0.0
    service_charge = 0.0
    discount = 0.0
    covers = 0
    gpay = 0.0
    card = 0.0
    zomato = 0.0
    other = 0.0
    categories: List[Dict[str, Any]] = []

    if summary_row is not None:
        hdr = {
            pos_parser.norm_header(df.iloc[summary_row, j]): j
            for j in range(len(df.columns))
            if pos_parser.norm_header(df.iloc[summary_row, j])
        }
        if summary_row + 1 < len(df):
            data_row = df.iloc[summary_row + 1]
            for k, idx in hdr.items():
                v = pos_parser.f(data_row.iloc[idx])
                if "net sales" in k or "my amount" in k:
                    net = max(net, v)
                elif "total" == k:
                    gross = max(gross, v)
                elif "cash" in k:
                    cash = max(cash, v)
                elif "cgst" in k:
                    cgst = v
                elif "sgst" in k:
                    sgst = v
                elif "service charge" in k:
                    service_charge = v
                elif "discount" in k:
                    discount = v
                elif "pax" in k:
                    covers = int(v)
        if gross == 0:
            gross = net

    # Payment section
    pay_start: Optional[int] = None
    for i in range(len(df)):
        label = pos_parser.norm_header(df.iloc[i, 0])
        if "payment wise" in label or label == "payment type":
            pay_start = i + 1
            break
    if pay_start:
        for i in range(pay_start, min(pay_start + 25, len(df))):
            label = pos_parser.norm_header(df.iloc[i, 0])
            if not label or "category" in label or label == "total":
                break
            amt = pos_parser.f(df.iloc[i, 1]) if len(df.columns) > 1 else 0.0
            bucket = pos_parser.payment_bucket(label)
            if bucket == "gpay":
                gpay += amt
            elif bucket == "zomato":
                zomato += amt
            elif bucket == "card":
                card += amt
            elif bucket == "cash":
                cash = max(cash, amt)
            else:
                other += amt

    # Category section
    cat_start: Optional[int] = None
    for i in range(len(df)):
        if "category wise" in pos_parser.norm_header(df.iloc[i, 0]):
            cat_start = i + 1
            break
    if cat_start is not None and cat_start < len(df):
        # Find amount column
        amt_col = 1
        for j in range(len(df.columns)):
            k = pos_parser.norm_header(df.iloc[cat_start, j])
            if "net sales" in k or "my amount" in k:
                amt_col = j
                break
        for i in range(cat_start + 1, min(cat_start + 30, len(df))):
            cat_name = str(df.iloc[i, 0]).strip() if pd.notna(df.iloc[i, 0]) else ""
            if not cat_name or cat_name.lower() in ("total", "round off", "nan", ""):
                if cat_name.lower() == "total":
                    break
                continue
            cat_amount = (
                pos_parser.f(df.iloc[i, amt_col]) if amt_col < len(df.columns) else 0.0
            )
            if cat_amount > 0:
                categories.append(
                    {
                        "category": pos_parser.normalize_group_category(cat_name),
                        "qty": 0,
                        "amount": cat_amount,
                    }
                )

    if net <= 0 and gross <= 0:
        return None, [f"Flash Report {filename}: no usable net/gross sales found."]

    return [
        {
            "date": date_str,
            "filename": filename,
            "file_type": "flash_report",
            "gross_total": gross,
            "net_total": net,
            "cash_sales": cash,
            "card_sales": card,
            "gpay_sales": gpay,
            "zomato_sales": zomato,
            "other_sales": other,
            "discount": discount,
            "complimentary": 0.0,
            "cgst": cgst,
            "sgst": sgst,
            "service_charge": service_charge,
            "covers": covers,
            "categories": categories,
            "services": [],
        }
    ], notes


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
    file_results: List[FileResult] = []
    global_notes: List[str] = []

    # Step 1 — classify every file
    classified: Dict[str, List[Tuple[str, bytes]]] = defaultdict(list)
    for fname, content in files:
        kind, label = file_detector.detect_and_describe(content, fname)
        importable = file_detector.is_importable(kind)
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
            parsed, dr_notes = dynamic_report_parser.parse_dynamic_report(
                content, fname
            )
            for n in dr_notes:
                global_notes.append(n)
            if parsed:
                fragments.extend(parsed)
                dynamic_dates = {f["date"] for f in parsed}
                if fr_match:
                    fr_match.notes.append(
                        f"Parsed {len(parsed)} day(s) from Dynamic Report."
                    )
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
                        fr_match.notes.append(
                            f"Added {new_days} day(s) not in Dynamic Report."
                        )
                    elif dynamic_dates:
                        fr_match.notes.append(
                            "All dates already covered by Dynamic Report."
                        )
                    else:
                        fr_match.notes.append(
                            f"Parsed {len(parsed)} day(s) of sales data."
                        )
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

    item_dates = {
        f["date"] for f in fragments if f.get("file_type") == "item_order_details"
    }

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
                    fr_match.notes.append(
                        f"Added {new_days} day(s) not in Item Report."
                    )
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

            # Basic validation / coercion
            if not merged.get("net_total") and merged.get("gross_total"):
                merged["net_total"] = float(merged["gross_total"])
            if not merged.get("gross_total") and merged.get("net_total"):
                merged["gross_total"] = float(merged["net_total"])

            ok, verr = pos_parser.validate_data(merged)
            day_results.append(
                DayResult(
                    date=d,
                    merged=merged,
                    source_kinds=source_kinds,
                    errors=(verr if not ok else []),
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
                merged["net_total"] = float(merged["gross_total"])
            if not merged.get("gross_total") and merged.get("net_total"):
                merged["gross_total"] = float(merged["net_total"])

            ok, verr = pos_parser.validate_data(merged)
            day_results.append(
                DayResult(
                    date=d,
                    merged=merged,
                    source_kinds=source_kinds,
                    errors=(verr if not ok else []),
                )
            )

        # Route untagged to the first available location (or fallback to provided location_id)
        fallback_loc = location_id or next(iter(location_results), None)
        if fallback_loc is not None:
            location_results.setdefault(fallback_loc, []).extend(day_results)
        else:
            # No dynamic report and no fallback — use a sentinel key so data isn't lost
            location_results[location_id] = day_results

    return SmartUploadResult(
        files=file_results,
        days=[],  # deprecated; use location_results
        global_notes=global_notes,
        location_results=location_results,
    )


def save_smart_upload_results(
    result: SmartUploadResult,
    location_id: int,
    uploaded_by: str,
    monthly_target: float = 0.0,
    daily_target: float = 0.0,
    seat_count: Optional[int] = None,
) -> Tuple[int, int, List[str]]:
    """
    Save data using the new simplified schema:
    - Raw bill_items stored in bill_items table
    - Aggregates derived at query time into daily_summary and category_summary

    Args:
        result: SmartUploadResult from process_smart_upload
        location_id: Target location ID
        uploaded_by: Username who uploaded
        monthly_target: Monthly sales target (optional)
        daily_target: Daily sales target (optional)
        seat_count: Number of seats (optional)

    Returns (saved_count, skipped_count, messages).
    """
    from collections import defaultdict
    from database import use_supabase, get_supabase_client
    import database_writes as db_writes

    saved = 0
    skipped = 0
    messages: List[str] = []

    if not use_supabase():
        return 0, 0, ["Supabase not configured - cannot save data"]

    client = get_supabase_client()
    if client is None:
        return 0, 0, ["Could not connect to Supabase"]

    dynamic_files = [
        fr for fr in result.files if fr.kind == "dynamic_report" and fr.content
    ]
    if not dynamic_files:
        return 0, 1, ["No Dynamic Report files found to save"]

    for fr in dynamic_files:
        if fr.error:
            skipped += 1
            messages.append(f"Skipped {fr.filename}: {fr.error}")
            continue

        try:
            raw_records, parse_notes = dynamic_report_parser.parse_dynamic_report_raw(
                fr.content, fr.filename
            )
            for note in parse_notes:
                messages.append(note)

            if not raw_records:
                skipped += 1
                messages.append(f"No data in {fr.filename}")
                continue

            restaurant_name = (
                raw_records[0].get("restaurant", "") if raw_records else ""
            )
            csv_location_id = db_writes._get_location_id(restaurant_name)

            if csv_location_id != location_id:
                messages.append(
                    f"{fr.filename}: restaurant '{restaurant_name}' mapped to "
                    f"location {csv_location_id}, but saving to {location_id}"
                )

            bill_items_to_save = []
            dates_processed = set()
            categories_by_date: Dict[str, Dict[str, Dict]] = defaultdict(
                lambda: {"qty": defaultdict(int), "net_amount": defaultdict(float)}
            )
            daily_agg: Dict[str, Dict] = defaultdict(
                lambda: {
                    "gross_total": 0.0,
                    "net_total": 0.0,
                    "covers": 0,
                    "discount": 0.0,
                    "cgst": 0.0,
                    "sgst": 0.0,
                    "service_charge": 0.0,
                    "gst_on_service_charge": 0.0,
                    "cancelled_amount": 0.0,
                    "complementary_amount": 0.0,
                    "bill_nos": set(),
                }
            )

            for rec in raw_records:
                bill_date = rec.get("bill_date", "")
                bill_no = rec.get("bill_no", "")
                bill_status = rec.get("bill_status", "")

                if bill_status.lower() in ("", "successorder"):
                    categories_by_date[bill_date]["qty"][
                        rec.get("category_name", "")
                    ] += rec.get("item_qty", 0)
                    categories_by_date[bill_date]["net_amount"][
                        rec.get("category_name", "")
                    ] += rec.get("net_amount", 0)

                agg = daily_agg[bill_date]
                agg["gross_total"] += rec.get("gross_amount", 0)
                agg["net_total"] += rec.get("net_amount", 0)
                agg["covers"] = rec.get("pax", 0)
                agg["discount"] += rec.get("discount", 0)
                agg["cgst"] += rec.get("cgst", 0)
                agg["sgst"] += rec.get("sgst", 0)
                agg["service_charge"] += rec.get("service_charge", 0)
                agg["gst_on_service_charge"] += rec.get("gst_on_service_charge", 0)
                agg["cancelled_amount"] += rec.get("cancelled_amount", 0)
                agg["complementary_amount"] += rec.get("complementary_amount", 0)
                if bill_no:
                    agg["bill_nos"].add(bill_no)
                dates_processed.add(bill_date)

                bill_items_to_save.append(rec)

            bill_items_to_save = [
                {k: v for k, v in rec.items() if k != "pax"}
                for rec in bill_items_to_save
            ]

            try:
                db_writes.save_bill_items(client, bill_items_to_save)
                messages.append(
                    f"Saved {len(bill_items_to_save)} bill items from {fr.filename}"
                )
            except Exception as e:
                messages.append(f"Error saving bill items: {e}")

            for date_str, agg in sorted(daily_agg.items()):
                daily_data = {
                    "gross_total": round(agg["gross_total"], 2),
                    "net_total": round(agg["net_total"], 2),
                    "covers": agg["covers"],
                    "discount": round(agg["discount"], 2),
                    "cgst": round(agg["cgst"], 2),
                    "sgst": round(agg["sgst"], 2),
                    "service_charge": round(agg["service_charge"], 2),
                    "gst_on_service_charge": round(agg["gst_on_service_charge"], 2),
                    "cancelled_amount": round(agg["cancelled_amount"], 2),
                    "complementary_amount": round(agg["complementary_amount"], 2),
                }
                try:
                    db_writes.save_daily_summary(
                        client, location_id, date_str, daily_data
                    )
                except Exception as e:
                    messages.append(f"Error saving daily summary for {date_str}: {e}")

            cat_records = []
            for date_str, cat_data in categories_by_date.items():
                for cat_name, qty in cat_data["qty"].items():
                    net_amt = cat_data["net_amount"].get(cat_name, 0.0)
                    cat_records.append(
                        {
                            "location_id": location_id,
                            "date": date_str,
                            "category_name": cat_name,
                            "net_amount": round(net_amt, 2),
                            "qty": qty,
                        }
                    )

            if cat_records:
                try:
                    db_writes.save_category_summary_batch(client, cat_records)
                    messages.append(
                        f"Saved {len(cat_records)} category summary records"
                    )
                except Exception as e:
                    messages.append(f"Error saving category summaries: {e}")

            for date_str in sorted(dates_processed):
                fnames = fr.filename
                primary_kind = "dynamic_report"
                database.save_upload_record(
                    location_id,
                    date_str,
                    fnames,
                    primary_kind,
                    uploaded_by,
                )

            saved += len(dates_processed)
            messages.append(
                f"Processed {len(dates_processed)} day(s) from {fr.filename}"
            )

        except Exception as e:
            skipped += 1
            messages.append(f"Error processing {fr.filename}: {e}")
            logger.exception("Failed to save smart upload result")

    return saved, skipped, messages
