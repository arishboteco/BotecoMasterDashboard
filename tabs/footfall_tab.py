"""Footfall tab — manual override of daily Lunch/Dinner cover counts."""

from __future__ import annotations

from datetime import date as date_cls
from typing import Optional

import streamlit as st

from components import (
    classed_container,
    filter_strip,
    info_banner,
    page_shell,
    section_title,
)
from components.footfall_editor import fetch_dates_with_data, render_footfall_editor
from tabs import TabContext


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

    with shell.filters:
        with classed_container(
            "tab-footfall-mobile-filters",
            "mobile-layout-stack",
            "mobile-layout-filters",
        ):
            filter_strip(
                "Footfall overrides",
                "Select a date range and outlet, then edit Lunch/Dinner covers inline.",
                icon="tune",
            )

            outlet_options = {int(loc["id"]): loc["name"] for loc in visible_locs}
            default_id = _default_outlet_id(ctx)
            option_ids = list(outlet_options.keys())
            try:
                default_index = option_ids.index(default_id) if default_id is not None else 0
            except ValueError:
                default_index = 0

            f1, f2, f3 = st.columns([1, 1, 2])
            with f1:
                start_date = st.date_input("From", value=month_start, key="footfall_start_date")
            with f2:
                end_date = st.date_input("To", value=today, key="footfall_end_date")
            with f3:
                selected_outlet_id = st.selectbox(
                    "Outlet",
                    options=option_ids,
                    index=default_index,
                    format_func=lambda i: outlet_options[i],
                    key="footfall_override_outlet",
                )

    if start_date > end_date:
        with shell.content:
            st.warning("'From' date must be before 'To' date.")
        return

    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")
    loc_name = outlet_options[selected_outlet_id]
    edited_by = str(st.session_state.get("username") or "")

    with shell.content:
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
