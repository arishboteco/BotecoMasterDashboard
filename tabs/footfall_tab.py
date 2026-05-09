"""Footfall tab — manual override of daily Lunch/Dinner cover counts."""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import date as date_cls
from datetime import datetime
from typing import Any, Optional

import pandas as pd
import streamlit as st

from components import (
    classed_container,
    info_banner,
    page_shell,
    section_title,
)
from components.footfall_editor import fetch_dates_with_data, render_footfall_editor
from repositories.footfall_override_repository import get_footfall_override_repository
from services.cache_invalidation import invalidate_footfall_caches
from tabs import TabContext


@dataclass
class BulkParseResult:
    required_headers_present: bool
    rows: list[dict[str, str]]
    errors: list[str]


def _parse_date_to_iso(date_text: str) -> str | None:
    value = str(date_text or "").strip()
    if not value:
        return None
    formats = ["%a, %d %B %Y", "%a, %d %b %Y", "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"]
    for fmt in formats:
        try:
            return datetime.strptime(value, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    try:
        return pd.to_datetime(value).strftime("%Y-%m-%d")
    except Exception:
        return None


def _parse_bulk_footfall_text(text: str) -> BulkParseResult:
    raw = str(text or "").strip()
    if not raw:
        return BulkParseResult(False, [], ["No pasted text found."])

    delimiter = "\t" if "\t" in raw else ","
    line_reader = csv.reader(io.StringIO(raw), delimiter=delimiter)
    all_rows = list(line_reader)
    if not all_rows:
        return BulkParseResult(False, [], ["No pasted rows found."])

    headers = [str(h or "").strip() for h in all_rows[0] if str(h or "").strip()]
    header_map = {h.strip().lower(): h for h in headers}
    required = ["date", "service", "covers"]
    missing = [h for h in required if h not in header_map]
    if missing:
        return BulkParseResult(
            False,
            [],
            [f"Missing required header(s): {', '.join(missing)}"],
        )

    rows: list[dict[str, str]] = []
    for cells in all_rows[1:]:
        row_cells = list(cells)
        if delimiter == "," and len(row_cells) > len(headers):
            extra = len(row_cells) - len(headers)
            date_parts = row_cells[: extra + 1]
            row_cells = [",".join(date_parts)] + row_cells[extra + 1 :]

        row_dict = {
            headers[idx]: (row_cells[idx] if idx < len(row_cells) else "")
            for idx in range(len(headers))
        }

        rows.append(
            {
                "date": str(row_dict.get(header_map["date"], "") or "").strip(),
                "brand": str(row_dict.get(header_map.get("brand", ""), "") or "").strip(),
                "service": str(row_dict.get(header_map["service"], "") or "").strip(),
                "covers": str(row_dict.get(header_map["covers"], "") or "").strip(),
            }
        )

    return BulkParseResult(True, rows, [])


def _normalize_bulk_rows(
    rows: list[dict[str, str]],
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    normalized: list[dict[str, Any]] = []
    invalid: list[dict[str, str]] = []
    for idx, row in enumerate(rows, start=1):
        service = str(row.get("service", row.get("Service", "")) or "").strip().lower()
        if service not in {"lunch", "dinner"}:
            invalid.append({"row": str(idx), "reason": "Service must be Lunch or Dinner"})
            continue

        iso_date = _parse_date_to_iso(str(row.get("date", row.get("Date", "")) or ""))
        if not iso_date:
            invalid.append({"row": str(idx), "reason": "Invalid date"})
            continue

        covers_text = str(row.get("covers", row.get("Covers", "")) or "").strip()
        if not covers_text.isdigit():
            invalid.append({"row": str(idx), "reason": "Covers must be a non-negative integer"})
            continue

        normalized.append(
            {
                "date": iso_date,
                "service": service,
                "covers": int(covers_text),
                "brand": str(row.get("brand", row.get("Brand", "")) or "").strip(),
            }
        )

    return normalized, invalid


def _group_bulk_rows_by_date(normalized_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for row in normalized_rows:
        date_key = str(row["date"])
        if date_key not in grouped:
            grouped[date_key] = {
                "date": date_key,
                "lunch_covers": None,
                "dinner_covers": None,
            }
        if row["service"] == "lunch":
            grouped[date_key]["lunch_covers"] = int(row["covers"])
        if row["service"] == "dinner":
            grouped[date_key]["dinner_covers"] = int(row["covers"])

    return [grouped[k] for k in sorted(grouped.keys())]


def _apply_bulk_overrides(
    location_id: int,
    edited_by: str,
    grouped_rows: list[dict[str, Any]],
) -> dict[str, int]:
    if not grouped_rows:
        return {"created": 0, "skipped_existing": 0}

    repo = get_footfall_override_repository()
    min_date = min(str(r["date"]) for r in grouped_rows)
    max_date = max(str(r["date"]) for r in grouped_rows)
    existing = repo.get_for_range([location_id], min_date, max_date)
    existing_dates = {str(r["date"]) for r in existing}

    created = 0
    skipped_existing = 0

    for row in grouped_rows:
        date_key = str(row["date"])
        if date_key in existing_dates:
            skipped_existing += 1
            continue

        repo.upsert(
            location_id,
            date_key,
            lunch_covers=row.get("lunch_covers"),
            dinner_covers=row.get("dinner_covers"),
            note=None,
            edited_by=edited_by,
        )
        created += 1

    if created > 0:
        invalidate_footfall_caches([location_id])

    return {"created": created, "skipped_existing": skipped_existing}


def _default_outlet_id(ctx: TabContext) -> Optional[int]:
    visible = [int(i) for i in (ctx.report_loc_ids or [])]
    if not visible:
        return None
    if ctx.location_id and int(ctx.location_id) in visible:
        return int(ctx.location_id)
    return visible[0]


def render(ctx: TabContext) -> None:
    """Render the Footfall override tab."""
    if not st.session_state.get("authenticated"):
        st.stop()

    shell = page_shell()

    visible_locs = [
        loc for loc in (ctx.all_locs or []) if int(loc["id"]) in (ctx.report_loc_ids or [])
    ]
    visible_locs.sort(key=lambda x: x["name"])

    if not visible_locs:
        with shell.content:
            info_banner(
                "No outlets are visible to your account. Ask an admin to assign you "
                "an outlet before entering footfall numbers.",
                tone="warning",
            )
        return

    today = date_cls.today()
    month_start = today.replace(day=1)

    outlet_names = [loc["name"] for loc in visible_locs]
    outlet_id_by_name = {loc["name"]: int(loc["id"]) for loc in visible_locs}
    default_id = _default_outlet_id(ctx)
    default_name = next(
        (loc["name"] for loc in visible_locs if int(loc["id"]) == default_id),
        outlet_names[0],
    )

    with shell.filters:
        with classed_container(
            "tab-footfall-mobile-filters",
            "mobile-layout-stack",
            "mobile-layout-filters",
        ):
            date_col, outlet_col = st.columns([1, 2])
            with date_col:
                date_range = st.date_input(
                    "Date range",
                    value=(month_start, today),
                    key="footfall_date_range",
                )
            with outlet_col:
                selected_outlet_name = st.pills(
                    "Outlet",
                    options=outlet_names,
                    default=default_name,
                    key="footfall_outlet_selector",
                    label_visibility="collapsed",
                ) or default_name

    if isinstance(date_range, (list, tuple)):
        if len(date_range) == 2:
            start_date, end_date = date_range[0], date_range[1]
        else:
            start_date = end_date = date_range[0]
    else:
        start_date = end_date = date_range or today

    if start_date > end_date:
        with shell.content:
            st.warning("'From' date must be before 'To' date.")
        return

    selected_outlet_id = outlet_id_by_name[selected_outlet_name]
    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")
    loc_name = selected_outlet_name
    edited_by = str(st.session_state.get("username") or "")

    with shell.content:
        mode = st.segmented_control(
            "Mode",
            options=["Edit covers", "Bulk paste"],
            default="Edit covers",
            key="footfall_mode",
            label_visibility="collapsed",
        ) or "Edit covers"

        st.divider()

        if mode == "Edit covers":
            section_title("Footfall covers", icon="people")
            st.caption(
                "Rows marked **✓ Set** already have an override saved. "
                "Rows marked **○ Not set** will use POS-derived values. "
                "Leave Lunch or Dinner blank to keep using the POS value for that service."
            )

            dates = fetch_dates_with_data(int(selected_outlet_id), start_str, end_str)

            if not dates:
                info_banner(
                    f"No imported data found for **{loc_name}** between {start_str} and {end_str}. "
                    "Upload a Growth Report first, then return here to enter footfall.",
                    tone="neutral",
                    icon="info",
                )
                return

            changed = render_footfall_editor(
                location_id=int(selected_outlet_id),
                dates=dates,
                loc_name=loc_name,
                edited_by=edited_by,
                key_prefix="footfall_tab_",
            )
            if changed:
                st.rerun()

        else:
            section_title("Bulk paste overrides", icon="content_paste")
            st.caption(
                "Paste rows with Date, Service, Covers (Brand optional). "
                "Selected outlet is used for all rows; existing override dates are skipped."
            )
            bulk_text = st.text_area(
                "Paste table rows",
                key="footfall_bulk_paste_text",
                height=220,
                help="Supports tab-delimited paste from Google Sheets/Excel and CSV text.",
            )

            parsed_key = "footfall_bulk_parsed"
            invalid_key = "footfall_bulk_invalid"
            grouped_key = "footfall_bulk_grouped"

            if st.button("Preview parsed rows", key="footfall_bulk_preview"):
                parse_result = _parse_bulk_footfall_text(bulk_text)
                if not parse_result.required_headers_present:
                    st.session_state[parsed_key] = []
                    st.session_state[invalid_key] = [
                        {"row": "-", "reason": msg} for msg in parse_result.errors
                    ]
                    st.session_state[grouped_key] = []
                else:
                    normalized, invalid_rows = _normalize_bulk_rows(parse_result.rows)
                    grouped_rows = _group_bulk_rows_by_date(normalized)
                    st.session_state[parsed_key] = normalized
                    st.session_state[invalid_key] = invalid_rows
                    st.session_state[grouped_key] = grouped_rows

            grouped_rows = list(st.session_state.get(grouped_key, []))
            invalid_rows = list(st.session_state.get(invalid_key, []))

            if invalid_rows:
                st.warning(f"{len(invalid_rows)} row(s) are invalid.")
                st.dataframe(pd.DataFrame(invalid_rows), use_container_width=True, hide_index=True)

            if grouped_rows:
                st.caption(f"Preview: {len(grouped_rows)} date row(s) ready to apply.")
                st.dataframe(pd.DataFrame(grouped_rows), use_container_width=True, hide_index=True)

            if st.button(
                "Apply bulk upload",
                key="footfall_bulk_apply",
                disabled=not bool(grouped_rows),
                type="primary",
            ):
                summary = _apply_bulk_overrides(
                    location_id=int(selected_outlet_id),
                    edited_by=edited_by,
                    grouped_rows=grouped_rows,
                )
                st.success(
                    f"Created {summary['created']} override(s). "
                    f"Skipped {summary['skipped_existing']} existing date(s)."
                )
                if summary["created"] > 0:
                    st.rerun()
