"""Date navigation component for report tabs."""

from __future__ import annotations

from datetime import datetime, timedelta

import streamlit as st


def date_nav(
    session_key: str = "report_date",
    label: str = "Select a date",
    help_text: str = "Choose a date to view that day's report",
) -> datetime:
    """Render date navigation with prev/next buttons and date picker."""
    if session_key not in st.session_state:
        st.session_state[session_key] = datetime.now().date()

    selected_date = st.session_state[session_key]
    date_display = selected_date.strftime("%a, %d %b %Y")

    nav_col1, nav_col2, nav_col3 = st.columns([1, 4, 1])
    with nav_col1:
        if st.button(
            "\u2190 Prev", key=f"{session_key}_prev", use_container_width=True
        ):
            st.session_state[session_key] -= timedelta(days=1)
            st.rerun()
    with nav_col2:
        st.markdown(
            f'<div class="date-display" style="text-align:center;">{date_display}</div>',
            unsafe_allow_html=True,
        )
    with nav_col3:
        if st.button(
            "Next \u2192", key=f"{session_key}_next", use_container_width=True
        ):
            st.session_state[session_key] += timedelta(days=1)
            st.rerun()

    picked = st.date_input(
        label,
        value=selected_date,
        key=f"{session_key}_picker",
        help=help_text,
        format="DD/MM/YYYY",
    )
    if picked != selected_date:
        st.session_state[session_key] = picked
        st.rerun()

    return selected_date


def date_range_nav(
    session_key_start: str,
    session_key_end: str,
    label_start: str = "From",
    label_end: str = "To",
) -> tuple[datetime.date, datetime.date]:
    """Render a side-by-side date range selector (From / To) with validation."""
    today = datetime.now().date()

    if session_key_start not in st.session_state:
        st.session_state[session_key_start] = today - timedelta(days=29)
    if session_key_end not in st.session_state:
        st.session_state[session_key_end] = today

    col_start, col_end = st.columns(2)
    with col_start:
        start_date = st.date_input(
            label_start,
            value=st.session_state[session_key_start],
            key=session_key_start,
            format="DD/MM/YYYY",
        )
    with col_end:
        end_date = st.date_input(
            label_end,
            value=st.session_state[session_key_end],
            key=session_key_end,
            format="DD/MM/YYYY",
        )

    if start_date > end_date:
        st.warning(
            f"Start date ({start_date.strftime('%d/%m/%Y')}) cannot be after "
            f"end date ({end_date.strftime('%d/%m/%Y')})."
        )
        return (
            st.session_state.get(session_key_start, start_date),
            st.session_state.get(session_key_end, end_date),
        )

    st.session_state[session_key_start] = start_date
    st.session_state[session_key_end] = end_date
    return start_date, end_date
