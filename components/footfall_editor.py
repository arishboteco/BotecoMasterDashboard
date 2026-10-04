"""Shared footfall override data-editor component.

Renders a st.data_editor where each row is one business date.
Rows with an existing override show pre-filled values and a "✓ Set" status;
rows without show empty inputs and "○ Not set".

Used by:
  tabs/footfall_tab.py  — date-range picker view
  tabs/upload_tab.py    — post-import step for just-imported dates
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import streamlit as st

import database
from repositories.footfall_override_repository import get_footfall_override_repository
from services.cache_invalidation import invalidate_footfall_caches

# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------


def _fetch_pos_covers_batch(location_id: int, dates: List[str]) -> Dict[str, Optional[int]]:
    """Return {date: total_covers} from daily_summary for the given dates.

    Falls back to order_count when covers is 0 or NULL (older imported rows).
    """
    if not dates:
        return {}

    def _best_covers(row: dict) -> Optional[int]:
        covers = row.get("covers")
        if covers:
            return int(covers)
        order_count = row.get("order_count")
        return int(order_count) if order_count else None

    if database.use_supabase():
        result = (
            database.get_supabase_client()
            .table("daily_summary")
            .select("date,covers,order_count")
            .eq("location_id", location_id)
            .in_("date", dates)
            .execute()
        )
        return {row["date"]: _best_covers(row) for row in (result.data or [])}

    with database.db_connection() as conn:
        placeholders = ",".join("?" * len(dates))
        cur = conn.cursor()
        cur.execute(
            f"SELECT date, covers, order_count FROM daily_summaries "
            f"WHERE location_id = ? AND date IN ({placeholders})",
            [location_id, *dates],
        )
        return {row["date"]: _best_covers(dict(row)) for row in cur.fetchall()}


def fetch_dates_with_data(location_id: int, start_date: str, end_date: str) -> List[str]:
    """Return sorted dates in [start, end] that have daily_summary data or overrides."""
    summary_dates: set[str] = set()

    if database.use_supabase():
        result = (
            database.get_supabase_client()
            .table("daily_summary")
            .select("date")
            .eq("location_id", location_id)
            .gte("date", start_date)
            .lte("date", end_date)
            .execute()
        )
        summary_dates = {row["date"] for row in (result.data or [])}
    else:
        with database.db_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT date FROM daily_summaries WHERE location_id = ? AND date BETWEEN ? AND ?",
                (location_id, start_date, end_date),
            )
            summary_dates = {row["date"] for row in cur.fetchall()}

    repo = get_footfall_override_repository()
    override_dates = {o["date"] for o in repo.get_for_range([location_id], start_date, end_date)}

    return sorted(summary_dates | override_dates)


# ---------------------------------------------------------------------------
# Public component
# ---------------------------------------------------------------------------


def render_footfall_inputs(
    location_id: int,
    dates: List[str],
    key_prefix: str = "",
    *,
    show_context: bool = True,
) -> Tuple[pd.DataFrame, Dict[str, Dict[str, Any]]]:
    """Render editable covers and return the draft plus its saved baseline.

    Call inside a form to let users enter every date before submitting.
    """
    if not dates:
        st.caption("No dates with imported data in this range.")
        return pd.DataFrame(), {}

    repo = get_footfall_override_repository()
    overrides = repo.get_for_range([location_id], min(dates), max(dates))
    overrides_by_date: Dict[str, Dict[str, Any]] = {o["date"]: o for o in overrides}

    pos_by_date = _fetch_pos_covers_batch(location_id, dates) if show_context else {}

    rows: List[Dict[str, Any]] = []
    for date in dates:
        ov = overrides_by_date.get(date)
        rows.append(
            {
                "Date": date,
                "POS Covers": pos_by_date.get(date),
                "Lunch": (
                    int(ov["lunch_covers"]) if ov and ov.get("lunch_covers") is not None else pd.NA
                ),
                "Dinner": (
                    int(ov["dinner_covers"])
                    if ov and ov.get("dinner_covers") is not None
                    else pd.NA
                ),
                "Status": "✓ Set" if ov else "○ Not set",
            }
        )

    df = pd.DataFrame(rows)
    df["Lunch"] = df["Lunch"].astype(pd.Int64Dtype())
    df["Dinner"] = df["Dinner"].astype(pd.Int64Dtype())

    # Snapshot original values keyed by date for change-detection
    original: Dict[str, Dict[str, Any]] = {
        r["Date"]: {
            "lunch": r["Lunch"],
            "dinner": r["Dinner"],
            "has_override": r["Date"] in overrides_by_date,
        }
        for r in rows
    }

    # Bump the key after each save so the editor resets to fresh DB values
    save_count_key = f"_footfall_save_count_{key_prefix}{location_id}"
    save_count = st.session_state.get(save_count_key, 0)
    editor_key = f"{key_prefix}footfall_editor_{location_id}_{save_count}"

    edited_df = st.data_editor(
        df,
        column_config={
            "Date": st.column_config.TextColumn("Date", disabled=True),
            "POS Covers": st.column_config.NumberColumn(
                "POS Covers",
                disabled=True,
                help="Total covers from POS data (read-only).",
            ),
            "Lunch": st.column_config.NumberColumn(
                "Lunch",
                width="small",
                min_value=0,
                step=1,
                help="Leave blank to use POS-derived value.",
            ),
            "Dinner": st.column_config.NumberColumn(
                "Dinner",
                width="small",
                min_value=0,
                step=1,
                help="Leave blank to use POS-derived value.",
            ),
            "Status": st.column_config.TextColumn("Status", disabled=True),
        },
        hide_index=True,
        column_order=(
            ["Date", "Lunch", "Dinner", "POS Covers", "Status"]
            if show_context
            else ["Date", "Lunch", "Dinner"]
        ),
        use_container_width=True,
        key=editor_key,
    )

    return edited_df, original


def save_footfall_values(
    location_id: int,
    edited_df: pd.DataFrame,
    original: Dict[str, Dict[str, Any]],
    edited_by: str,
) -> int:
    """Save changed cover counts, preserving blanks, zeroes and untouched dates."""
    repo = get_footfall_override_repository()
    changed = 0

    def _eq(a: Any, b: Any) -> bool:
        if pd.isna(a) and pd.isna(b):
            return True
        if pd.isna(a) or pd.isna(b):
            return False
        return int(a) == int(b)

    try:
        for _, row in edited_df.iterrows():
            date = str(row["Date"])
            orig = original.get(date, {})
            new_lunch, new_dinner = row["Lunch"], row["Dinner"]
            old_lunch = orig.get("lunch", pd.NA)
            old_dinner = orig.get("dinner", pd.NA)

            if _eq(new_lunch, old_lunch) and _eq(new_dinner, old_dinner):
                continue

            lc = None if pd.isna(new_lunch) else int(new_lunch)
            dc = None if pd.isna(new_dinner) else int(new_dinner)

            if lc is None and dc is None:
                if orig.get("has_override"):
                    repo.delete(location_id, date)
                    changed += 1
            else:
                repo.upsert(
                    location_id,
                    date,
                    lunch_covers=lc,
                    dinner_covers=dc,
                    note=None,
                    edited_by=edited_by,
                )
                changed += 1
    finally:
        # A later write can fail after earlier dates were saved.
        if changed:
            invalidate_footfall_caches([location_id])

    return changed


def render_footfall_editor(
    location_id: int,
    dates: List[str],
    loc_name: str,
    edited_by: str,
    key_prefix: str = "",
) -> int:
    """Render a batched footfall form; the caller refreshes after a save."""
    if not dates:
        st.caption("No dates with imported data in this range.")
        return 0

    with st.form(f"{key_prefix}footfall_form_{location_id}", enter_to_submit=False):
        edited_df, original = render_footfall_inputs(location_id, dates, key_prefix)
        submitted = st.form_submit_button(
            "Save footfall covers",
            type="primary",
        )

    if submitted:
        changed = save_footfall_values(location_id, edited_df, original, edited_by)

        if changed:
            save_count_key = f"_footfall_save_count_{key_prefix}{location_id}"
            st.session_state[save_count_key] = st.session_state.get(save_count_key, 0) + 1
            st.success(f"Saved {changed} footfall override(s) for {loc_name}.")
        else:
            st.info("No changes to save.")

        return changed

    return 0
