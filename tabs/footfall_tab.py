"""Footfall tab — manual lunch/dinner cover overrides."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, Optional

import pandas as pd
import streamlit as st

import database
import services.cache_invalidation as cache_invalidation
from components import classed_container, page_shell, section_title
from repositories.footfall_override_repository import get_footfall_override_repository
from tabs import TabContext


def _as_optional_int(value: Any) -> Optional[int]:
    """Normalize empty Streamlit number inputs to nullable override values."""
    if value is None:
        return None
    return int(value)


def _get_pos_covers(location_id: int, date_str: str) -> Dict[str, int]:
    """Fetch raw POS-derived covers, bypassing read-time override merging."""
    if database.use_supabase():
        supabase = database.get_supabase_client()
        result = (
            supabase.table("daily_summary")
            .select("lunch_covers,dinner_covers,covers")
            .eq("location_id", location_id)
            .eq("date", date_str)
            .execute()
        )
        row = (result.data or [None])[0]
        if not row:
            return {"lunch_covers": 0, "dinner_covers": 0, "covers": 0}
        return {
            "lunch_covers": int(row.get("lunch_covers") or 0),
            "dinner_covers": int(row.get("dinner_covers") or 0),
            "covers": int(row.get("covers") or 0),
        }

    with database.db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT lunch_covers, dinner_covers, covers
            FROM daily_summaries
            WHERE location_id = ? AND date = ?
            """,
            (location_id, date_str),
        )
        row = cursor.fetchone()
    if not row:
        return {"lunch_covers": 0, "dinner_covers": 0, "covers": 0}
    return {
        "lunch_covers": int(row["lunch_covers"] or 0),
        "dinner_covers": int(row["dinner_covers"] or 0),
        "covers": int(row["covers"] or 0),
    }


def _invalidate_footfall_caches(location_id: int) -> None:
    """Invalidate footfall caches, tolerating older deployed cache modules."""
    helper = getattr(cache_invalidation, "invalidate_footfall_caches", None)
    if helper is not None:
        helper(location_id)
        return

    cache_invalidation.invalidate_location_reads(location_id)
    cache_invalidation.invalidate_analytics()
    cache_invalidation.invalidate_reports()


def _recent_overrides(location_id: int, selected_date: date) -> pd.DataFrame:
    start = (selected_date - timedelta(days=13)).strftime("%Y-%m-%d")
    end = selected_date.strftime("%Y-%m-%d")
    rows = get_footfall_override_repository().get_for_range([location_id], start, end)
    if not rows:
        return pd.DataFrame()
    display_rows = []
    for row in reversed(rows):
        display_rows.append(
            {
                "Date": row.get("date"),
                "Lunch override": row.get("lunch_covers"),
                "Dinner override": row.get("dinner_covers"),
                "Note": row.get("note") or "",
                "Edited by": row.get("edited_by") or "",
                "Edited at": row.get("edited_at") or "",
            }
        )
    return pd.DataFrame(display_rows)


def render(ctx: TabContext) -> None:
    """Render the manual footfall override UI."""
    if not st.session_state.get("authenticated"):
        st.stop()

    shell = page_shell()
    repo = get_footfall_override_repository()
    allowed_locs = [loc for loc in ctx.all_locs if int(loc["id"]) in set(ctx.report_loc_ids)]

    with shell.hero:
        section_title(
            "Footfall overrides",
            subtitle="Correct Lunch and Dinner covers without editing POS imports.",
            icon="tune",
        )

    if not allowed_locs:
        st.warning("No outlets are available for your account.")
        st.stop()

    name_by_id = {int(loc["id"]): str(loc["name"]) for loc in allowed_locs}
    allowed_ids = list(name_by_id.keys())
    default_index = allowed_ids.index(ctx.location_id) if ctx.location_id in allowed_ids else 0

    with shell.filters:
        with classed_container(
            "tab-footfall-mobile-filters",
            "mobile-layout-stack",
            "mobile-layout-filters",
        ):
            f1, f2 = st.columns(2)
            with f1:
                selected_date = st.date_input("Date", value=date.today(), key="footfall_date")
            with f2:
                location_id = st.selectbox(
                    "Outlet",
                    options=allowed_ids,
                    index=default_index,
                    format_func=lambda loc_id: name_by_id[int(loc_id)],
                    key="footfall_location",
                )

    date_str = selected_date.strftime("%Y-%m-%d")
    location_id = int(location_id)
    pos = _get_pos_covers(location_id, date_str)
    override = repo.get(location_id, date_str)

    with shell.content:
        st.markdown("### Current covers")
        pos_col, override_col = st.columns(2)
        with pos_col:
            with st.container(border=True):
                st.markdown("**POS-calculated**")
                c1, c2, c3 = st.columns(3)
                c1.metric("Lunch", pos["lunch_covers"])
                c2.metric("Dinner", pos["dinner_covers"])
                c3.metric("Total", pos["covers"])
        with override_col:
            with st.container(border=True):
                st.markdown("**Current override**")
                if override:
                    lunch = override.get("lunch_covers")
                    dinner = override.get("dinner_covers")
                    total = int(lunch or pos["lunch_covers"]) + int(dinner or pos["dinner_covers"])
                    c1, c2, c3 = st.columns(3)
                    c1.metric("Lunch", "POS" if lunch is None else int(lunch))
                    c2.metric("Dinner", "POS" if dinner is None else int(dinner))
                    c3.metric("Effective total", total)
                    if override.get("note"):
                        st.caption(str(override["note"]))
                else:
                    st.info("No override saved for this outlet/date.")

        with st.form("footfall_override_form"):
            st.markdown("### Enter override")
            lunch_default = override.get("lunch_covers") if override else None
            dinner_default = override.get("dinner_covers") if override else None
            col1, col2 = st.columns(2)
            with col1:
                lunch_covers = st.number_input(
                    "Lunch covers override",
                    min_value=0,
                    value=lunch_default,
                    step=1,
                    placeholder="Leave blank to use POS",
                    help="Blank means Lunch continues to use the POS-calculated value.",
                )
            with col2:
                dinner_covers = st.number_input(
                    "Dinner covers override",
                    min_value=0,
                    value=dinner_default,
                    step=1,
                    placeholder="Leave blank to use POS",
                    help="Blank means Dinner continues to use the POS-calculated value.",
                )
            note = st.text_area(
                "Note",
                value=str(override.get("note") or "") if override else "",
                placeholder="Optional reason, e.g. manual event headcount",
            )
            save_col, clear_col = st.columns([1, 1])
            with save_col:
                save_clicked = st.form_submit_button("Save", type="primary")
            with clear_col:
                clear_clicked = st.form_submit_button("Clear override")

        if save_clicked:
            lunch_value = _as_optional_int(lunch_covers)
            dinner_value = _as_optional_int(dinner_covers)
            if lunch_value is None and dinner_value is None:
                st.error("Enter Lunch covers, Dinner covers, or both before saving.")
            else:
                repo.upsert(
                    location_id,
                    date_str,
                    lunch_covers=lunch_value,
                    dinner_covers=dinner_value,
                    note=note.strip() or None,
                    edited_by=str(st.session_state.get("username") or "unknown"),
                )
                _invalidate_footfall_caches(location_id)
                st.success("Footfall override saved.")
                st.rerun()

        if clear_clicked:
            if repo.delete(location_id, date_str):
                _invalidate_footfall_caches(location_id)
                st.success("Footfall override cleared.")
                st.rerun()
            else:
                st.info("No override exists for this outlet/date.")

        st.markdown("### Recent overrides for this outlet")
        recent_df = _recent_overrides(location_id, selected_date)
        if recent_df.empty:
            st.caption("No overrides in the last 14 days.")
        else:
            st.dataframe(recent_df, width="stretch", hide_index=True)
