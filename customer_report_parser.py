"""Parse customer_report.xlsx for outlet-specific cover counts (replaces POS-derived covers)."""

from __future__ import annotations

import re
from io import BytesIO
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from pos_parser import _cell_date_to_iso, _norm_header


CoverEntry = Dict[str, Any]
LookupMap = Dict[Tuple[int, str], CoverEntry]


def _norm(s: Any) -> str:
    if s is None or (isinstance(s, float) and pd.isna(s)):
        return ""
    return re.sub(r"\s+", " ", str(s).strip().lower())


def _col_idx(colmap: Dict[str, int], *needles: str) -> Optional[int]:
    """Find column index by keyword(s) with fuzzy matching."""
    if not needles:
        return None

    # First try: all needles must be present in key
    for key, idx in colmap.items():
        if all(n in key for n in needles):
            return idx

    # Second try: any needle matches (substring search)
    for key, idx in colmap.items():
        if any(n in key for n in needles):
            return idx

    # Third try: check for common variations
    variations = {
        "cover": [
            "covers",
            "pax",
            "guests",
            "footfall",
            "headcount",
            "head count",
            "diners",
            "patrons",
        ],
        "date": ["day", "booking date", "visit date"],
        "outlet": ["location", "branch", "store", "restaurant", "unit", "site"],
        "lunch": ["lunch covers", "lunch pax", "afternoon"],
        "dinner": ["dinner covers", "dinner pax", "evening"],
    }

    for needle in needles:
        if needle in variations:
            for variant in variations[needle]:
                for key, idx in colmap.items():
                    if variant in key:
                        return idx

    return None


def _match_location_id(
    outlet_raw: Any, locations: List[Dict[str, Any]]
) -> Optional[int]:
    o = _norm(outlet_raw)
    if not o:
        return None
    for loc in locations:
        name = _norm(loc.get("name", ""))
        if not name:
            continue
        if name in o or o in name:
            return int(loc["id"])
    if "indiqube" in o:
        for loc in locations:
            if "indiqube" in _norm(loc.get("name", "")):
                return int(loc["id"])
    if "bagmane" in o:
        for loc in locations:
            if "bagmane" in _norm(loc.get("name", "")):
                return int(loc["id"])
    return None


def _header_row_and_map(df: pd.DataFrame) -> Optional[Tuple[int, Dict[str, int]]]:
    for i in range(min(45, len(df))):
        parts = [_norm_header(x) for x in df.iloc[i].values if _norm_header(x)]
        joined = " ".join(parts)
        if "date" not in joined:
            continue
        if not any(
            x in joined
            for x in (
                "cover",
                "footfall",
                "pax",
                "guest",
                "customer",
                "dinner",
                "lunch",
            )
        ):
            continue
        colmap: Dict[str, int] = {}
        for j, v in enumerate(df.iloc[i]):
            k = _norm_header(v)
            if k:
                colmap[k] = j
        return i, colmap
    return None


def _parse_sheet(
    df: pd.DataFrame,
    locations: List[Dict[str, Any]],
    sheet_name_hint: str,
) -> LookupMap:
    out: LookupMap = {}
    hm = _header_row_and_map(df)
    if not hm:
        return out
    header_idx, colmap = hm
    idx_date = colmap.get("date") if "date" in colmap else _col_idx(colmap, "date")
    idx_outlet = _col_idx(colmap, "outlet", "branch", "location", "store", "restaurant")
    idx_covers = _col_idx(colmap, "cover")
    if idx_covers is None:
        idx_covers = _col_idx(colmap, "footfall")
    idx_lunch = _col_idx(colmap, "lunch")
    idx_dinner = _col_idx(colmap, "dinner")
    if idx_date is None or (
        idx_covers is None and idx_lunch is None and idx_dinner is None
    ):
        return out

    hint_id = _match_location_id(sheet_name_hint, locations)

    for ri in range(header_idx + 1, len(df)):
        row = df.iloc[ri]
        dcell = row.iloc[idx_date]
        if pd.isna(dcell):
            continue
        if str(dcell).strip().lower() == "total":
            continue
        day = _cell_date_to_iso(dcell)
        if not day:
            continue

        lid: Optional[int] = None
        if idx_outlet is not None:
            lid = _match_location_id(row.iloc[idx_outlet], locations)
        if lid is None:
            lid = hint_id
        if lid is None:
            continue

        lunch_v: Optional[int] = None
        dinner_v: Optional[int] = None
        if idx_lunch is not None and pd.notna(row.iloc[idx_lunch]):
            try:
                lunch_v = int(float(str(row.iloc[idx_lunch]).replace(",", "")))
            except ValueError:
                lunch_v = None
        if idx_dinner is not None and pd.notna(row.iloc[idx_dinner]):
            try:
                dinner_v = int(float(str(row.iloc[idx_dinner]).replace(",", "")))
            except ValueError:
                dinner_v = None

        covers = 0
        if idx_covers is not None and pd.notna(row.iloc[idx_covers]):
            try:
                covers = int(float(str(row.iloc[idx_covers]).replace(",", "")))
            except ValueError:
                covers = 0
        if lunch_v is not None and dinner_v is not None:
            covers = lunch_v + dinner_v
        elif covers == 0 and lunch_v is not None:
            covers = lunch_v
        elif covers == 0 and dinner_v is not None:
            covers = dinner_v

        key = (lid, day)
        out[key] = {
            "covers": covers,
            "lunch_covers": lunch_v,
            "dinner_covers": dinner_v,
        }
    return out


def build_covers_lookup(
    content: bytes, locations: List[Dict[str, Any]], debug: bool = False
) -> Tuple[LookupMap, List[str]]:
    """Parse workbook; returns (location_id, date) -> cover fields and notes."""
    notes: List[str] = []
    bio = BytesIO(content)
    bio.seek(0)
    try:
        xl = pd.ExcelFile(bio, engine="openpyxl")
    except Exception as ex:
        try:
            bio.seek(0)
            xl = pd.ExcelFile(bio, engine="xlrd")
        except Exception:
            notes.append(f"Could not open customer report: {ex}")
            return {}, notes

    combined: LookupMap = {}
    total_rows_found = 0

    for sheet_name in xl.sheet_names:
        try:
            bio.seek(0)
            df = pd.read_excel(bio, sheet_name=sheet_name, header=None, engine=None)
        except Exception:
            try:
                bio.seek(0)
                df = pd.read_excel(
                    bio, sheet_name=sheet_name, header=None, engine="openpyxl"
                )
            except Exception as ex2:
                notes.append(f"Skip sheet {sheet_name!r}: {ex2}")
                continue
        if df is None or df.empty:
            continue

        # Debug: Show first few rows to help diagnose issues
        if debug:
            notes.append(f"Sheet '{sheet_name}': {len(df)} rows, first 3 rows preview:")
            for i in range(min(3, len(df))):
                row_vals = [
                    str(v) if pd.notna(v) else "" for v in df.iloc[i].values[:5]
                ]
                notes.append(f"  Row {i}: {row_vals}")

        part = _parse_sheet(df, locations, sheet_name)

        if debug and not part:
            # Debug: Try to detect what went wrong
            hm = _header_row_and_map(df)
            if not hm:
                notes.append(
                    f"Sheet '{sheet_name}': No header row found (need 'date' + 'cover/footfall/pax/lunch/dinner')"
                )
            else:
                header_idx, colmap = hm
                notes.append(
                    f"Sheet '{sheet_name}': Header at row {header_idx}, columns: {list(colmap.keys())[:10]}..."
                )
                idx_date = (
                    colmap.get("date") if "date" in colmap else _col_idx(colmap, "date")
                )
                idx_covers = _col_idx(colmap, "cover") or _col_idx(colmap, "footfall")
                idx_lunch = _col_idx(colmap, "lunch")
                idx_dinner = _col_idx(colmap, "dinner")
                notes.append(
                    f"  Detected: date={idx_date}, covers={idx_covers}, lunch={idx_lunch}, dinner={idx_dinner}"
                )
        elif part:
            total_rows_found += len(part)
            if debug:
                notes.append(f"Sheet '{sheet_name}': Found {len(part)} cover entries")

        combined.update(part)

    if not combined:
        notes.append(
            "No cover rows found — expected columns like Date and Covers (or Lunch/Dinner)."
        )
    elif debug:
        notes.append(f"Total: Found {total_rows_found} cover entries across all sheets")

    return combined, notes


def apply_covers_overlay(
    merged: Dict[str, Any],
    location_id: int,
    lookup: LookupMap,
) -> Dict[str, Any]:
    """Replace covers from lookup for this location and date."""
    out = dict(merged)
    key = (location_id, str(out.get("date", ""))[:10])
    if key not in lookup:
        return out
    ent = lookup[key]
    out["covers"] = int(ent.get("covers") or 0)
    if ent.get("lunch_covers") is not None:
        out["lunch_covers"] = ent["lunch_covers"]
    if ent.get("dinner_covers") is not None:
        out["dinner_covers"] = ent["dinner_covers"]
    return out


def load_lookup_from_path(
    path: str, locations: List[Dict[str, Any]], debug: bool = False
) -> Tuple[LookupMap, List[str]]:
    if not path or not path.strip():
        return {}, ["Customer report path is not set."]
    try:
        with open(path, "rb") as f:
            return build_covers_lookup(f.read(), locations, debug=debug)
    except OSError as ex:
        return {}, [f"Cannot read customer report file: {ex}"]
