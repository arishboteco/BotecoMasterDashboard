"""Shared footfall override data-editor component.

Renders a st.data_editor where each row is one business date.
Rows with an existing override show pre-filled values and a "✓ Set" status;
rows without show empty inputs and "○ Not set".

Used by:
  tabs/footfall_tab.py  — date-range picker view
  tabs/upload_tab.py    — post-import step for just-imported dates
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import pandas as pd
import streamlit as st

import database
from repositories.footfall_override_repository import get_footfall_override_repository
from services.cache_invalidation import invalidate_footfall_caches


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------


def _fetch_pos_covers_batch(
    location_id: int, dates: List[str]
) -> Dict[str, Optional[int]]:
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


def fetch_dates_with_data(
    location_id: int, start_date: str, end_date: str
) -> List[str]:
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
                "SELECT date FROM daily_summaries "
                "WHERE location_id = ? AND date BETWEEN ? AND ?",
                (location_id, start_date, end_date),
            )
            summary_dates = {row["date"] for row in cur.fetchall()}

    repo = get_footfall_override_repository()
    override_dates = {
        o["date"]
        for o in repo.get_for_range([location_id], start_date, end_date)
    }

    return sorted(summary_dates | override_dates)


# ---------------------------------------------------------------------------
# Public component
# ---------------------------------------------------------------------------


def render_footfall_editor(
    location_id: int,
    dates: List[str],
    loc_name: str,
    edited_by: str,
    key_prefix: str = "",
) -> int:
    """Render a data_editor for footfall override entry.

    Each row represents one date. Rows with existing overrides show "✓ Set"
    and pre-filled Lunch/Dinner values; rows without show "○ Not set" and
    empty inputs. The POS Total column is read-only context.

    Returns the number of rows that were changed (saved or deleted).
    Does NOT call st.rerun() — the caller decides when to rerun.
    """
    if not dates:
        st.caption("No dates with imported data in this range.")
        return 0

    repo = get_footfall_override_repository()
    overrides = repo.get_for_range([location_id], min(dates), max(dates))
    overrides_by_date: Dict[str, Dict[str, Any]] = {o["date"]: o for o in overrides}

    pos_by_date = _fetch_pos_covers_batch(location_id, dates)

    rows: List[Dict[str, Any]] = []
    for date in dates:
        ov = overrides_by_date.get(date)
        rows.append(
            {
                "Date": date,
                "POS Covers": pos_by_date.get(date),
                "Lunch": (
                    int(ov["lunch_covers"])
                    if ov and ov.get("lunch_covers") is not None
                    else pd.NA
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
                "Lunch Covers",
                min_value=0,
                step=1,
                help="Leave blank to use POS-derived value.",
            ),
            "Dinner": st.column_config.NumberColumn(
                "Dinner Covers",
                min_value=0,
                step=1,
                help="Leave blank to use POS-derived value.",
            ),
            "Status": st.column_config.TextColumn("Status", disabled=True),
        },
        hide_index=True,
        use_container_width=True,
        key=editor_key,
    )

    if st.button(
        "Save footfall covers",
        key=f"{key_prefix}save_footfall_{location_id}",
        type="primary",
    ):
        changed = 0

        def _eq(a: Any, b: Any) -> bool:
            if pd.isna(a) and pd.isna(b):
                return True
            if pd.isna(a) or pd.isna(b):
                return False
            return int(a) == int(b)

        for _, row in edited_df.iterrows():
            date = str(row["Date"])
            orig = original.get(date, {})
            new_lunch, new_dinner = row["Lunch"], row["Dinner"]
            old_lunch = orig.get("lunch", pd.NA)
            old_dinner = orig.get("dinner", pd.NA)

            if _eq(new_lunch, old_lunch) and _eq(new_dinner, old_dinner):
                continue  # unchanged

            lc = None if pd.isna(new_lunch) else int(new_lunch)
            dc = None if pd.isna(new_dinner) else int(new_dinner)

            if lc is None and dc is None:
                # Both cleared → remove override if one existed
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

        if changed:
            invalidate_footfall_caches([location_id])
            st.session_state[save_count_key] = save_count + 1
            st.success(f"Saved {changed} footfall override(s) for {loc_name}.")
        else:
            st.info("No changes to save.")

        return changed

    return 0
