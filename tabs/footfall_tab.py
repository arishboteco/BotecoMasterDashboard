"""Footfall tab — manual override of daily Lunch/Dinner cover counts."""

from __future__ import annotations

from datetime import date as date_cls
from typing import Any, Dict, List, Optional

import pandas as pd
import streamlit as st

import database
from components import (
    classed_container,
    divider,
    filter_strip,
    info_banner,
    page_shell,
    section_title,
)
from repositories.footfall_override_repository import (
    get_footfall_override_repository,
)
from services.cache_invalidation import invalidate_footfall_caches
from tabs import TabContext

# Service-classification cutoffs match dynamic_report_parser.py and pos_parser.py.
LUNCH_HOURS = "12:00 – 17:59"
DINNER_HOURS = "18:00 onwards"


def _pos_covers_for(location_id: int, date_str: str) -> Dict[str, Optional[int]]:
    """Return raw POS-derived covers (without override overlay) for display."""
    with database.db_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT covers, lunch_covers, dinner_covers
            FROM daily_summaries
            WHERE location_id = ? AND date = ?
            """,
            (location_id, date_str),
        )
        row = cur.fetchone()
    if not row:
        return {"covers": None, "lunch_covers": None, "dinner_covers": None}
    return {
        "covers": int(row["covers"]) if row["covers"] is not None else None,
        "lunch_covers": (
            int(row["lunch_covers"]) if row["lunch_covers"] is not None else None
        ),
        "dinner_covers": (
            int(row["dinner_covers"]) if row["dinner_covers"] is not None else None
        ),
    }


def _recent_overrides(
    location_id: int, days: int = 14
) -> List[Dict[str, Any]]:
    """Fetch the most recent override rows for an outlet."""
    with database.db_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT date, lunch_covers, dinner_covers, note, edited_by, edited_at
            FROM footfall_overrides
            WHERE location_id = ?
            ORDER BY date DESC
            LIMIT ?
            """,
            (location_id, days),
        )
        rows = cur.fetchall()
    return [dict(r) for r in rows]


def _default_outlet_id(ctx: TabContext) -> Optional[int]:
    """Pick an initial outlet for the selectbox: home outlet if visible, else first allowed."""
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

    with shell.filters:
        with classed_container(
            "tab-footfall-mobile-filters",
            "mobile-layout-stack",
            "mobile-layout-filters",
        ):
            filter_strip(
                "Footfall override",
                "Pick a date and outlet to enter Lunch/Dinner covers manually.",
                icon="tune",
            )

            f1, f2 = st.columns([1, 2])
            with f1:
                if "footfall_override_date" not in st.session_state:
                    st.session_state["footfall_override_date"] = date_cls.today()
                selected_date: date_cls = st.date_input(
                    "Date",
                    key="footfall_override_date",
                )
            with f2:
                outlet_options = {int(loc["id"]): loc["name"] for loc in visible_locs}
                default_id = _default_outlet_id(ctx)
                option_ids = list(outlet_options.keys())
                try:
                    default_index = (
                        option_ids.index(default_id) if default_id is not None else 0
                    )
                except ValueError:
                    default_index = 0
                selected_outlet_id = st.selectbox(
                    "Outlet",
                    options=option_ids,
                    index=default_index,
                    format_func=lambda i: outlet_options[i],
                    key="footfall_override_outlet",
                )

    date_str = selected_date.strftime("%Y-%m-%d")
    repo = get_footfall_override_repository()
    pos_covers = _pos_covers_for(selected_outlet_id, date_str)
    existing = repo.get(selected_outlet_id, date_str)

    with shell.content:
        section_title("Override entry", icon="edit")

        with st.container(border=True):
            cur1, cur2, cur3 = st.columns(3)
            with cur1:
                st.markdown("**POS – Total covers**")
                st.markdown(
                    f"`{pos_covers['covers']}`"
                    if pos_covers["covers"] is not None
                    else "_no POS data_"
                )
            with cur2:
                st.markdown(f"**POS – Lunch** _( {LUNCH_HOURS} )_")
                st.markdown(
                    f"`{pos_covers['lunch_covers']}`"
                    if pos_covers["lunch_covers"] is not None
                    else "_no POS data_"
                )
            with cur3:
                st.markdown(f"**POS – Dinner** _( {DINNER_HOURS} )_")
                st.markdown(
                    f"`{pos_covers['dinner_covers']}`"
                    if pos_covers["dinner_covers"] is not None
                    else "_no POS data_"
                )

            if existing:
                edited_by = existing.get("edited_by") or "—"
                edited_at = existing.get("edited_at") or ""
                st.caption(
                    f"Current override: Lunch={existing.get('lunch_covers')}"
                    f", Dinner={existing.get('dinner_covers')}"
                    f" · last edited by **{edited_by}** at {edited_at}"
                )

        with st.form("footfall_override_form"):
            ff1, ff2 = st.columns(2)
            with ff1:
                lunch_default = (
                    int(existing["lunch_covers"])
                    if existing and existing.get("lunch_covers") is not None
                    else 0
                )
                lunch_value = st.number_input(
                    "Lunch covers",
                    min_value=0,
                    value=lunch_default,
                    step=1,
                    help=(
                        "Bills timestamped 12:00 – 17:59 fall under Lunch in the "
                        "automatic POS classification."
                    ),
                )
                lunch_blank = st.checkbox(
                    "Don't override Lunch (use POS value)",
                    value=existing is not None
                    and existing.get("lunch_covers") is None,
                    key="footfall_override_lunch_blank",
                )
            with ff2:
                dinner_default = (
                    int(existing["dinner_covers"])
                    if existing and existing.get("dinner_covers") is not None
                    else 0
                )
                dinner_value = st.number_input(
                    "Dinner covers",
                    min_value=0,
                    value=dinner_default,
                    step=1,
                    help="Bills timestamped 18:00 onward fall under Dinner.",
                )
                dinner_blank = st.checkbox(
                    "Don't override Dinner (use POS value)",
                    value=existing is not None
                    and existing.get("dinner_covers") is None,
                    key="footfall_override_dinner_blank",
                )

            note_value = st.text_area(
                "Note (optional)",
                value=(existing.get("note") or "") if existing else "",
                placeholder="Reason for override, source of head count, etc.",
            )

            sb1, sb2 = st.columns([1, 1])
            with sb1:
                save_clicked = st.form_submit_button(
                    "Save override", type="primary", width="stretch"
                )
            with sb2:
                clear_clicked = st.form_submit_button(
                    "Clear override",
                    width="stretch",
                    disabled=existing is None,
                )

        if save_clicked:
            lc_to_save = None if lunch_blank else int(lunch_value)
            dc_to_save = None if dinner_blank else int(dinner_value)
            if lc_to_save is None and dc_to_save is None:
                st.warning(
                    "Both Lunch and Dinner are set to use POS values — nothing to "
                    "override. Use **Clear override** to remove an existing entry."
                )
            else:
                repo.upsert(
                    int(selected_outlet_id),
                    date_str,
                    lunch_covers=lc_to_save,
                    dinner_covers=dc_to_save,
                    note=(note_value or None),
                    edited_by=str(st.session_state.get("username") or ""),
                )
                invalidate_footfall_caches([int(selected_outlet_id)])
                st.success(
                    f"Saved override for {outlet_options[selected_outlet_id]} on "
                    f"{date_str}."
                )
                st.rerun()

        if clear_clicked and existing is not None:
            repo.delete(int(selected_outlet_id), date_str)
            invalidate_footfall_caches([int(selected_outlet_id)])
            st.success(
                f"Cleared override for {outlet_options[selected_outlet_id]} on "
                f"{date_str}."
            )
            st.rerun()

        divider()

        section_title("Recent overrides", icon="history")
        recent = _recent_overrides(int(selected_outlet_id))
        if not recent:
            st.caption("No overrides recorded yet for this outlet.")
        else:
            df = pd.DataFrame(recent)
            df = df.rename(
                columns={
                    "date": "Date",
                    "lunch_covers": "Lunch",
                    "dinner_covers": "Dinner",
                    "note": "Note",
                    "edited_by": "Edited by",
                    "edited_at": "Edited at",
                }
            )
            st.dataframe(df, width="stretch", hide_index=True)
