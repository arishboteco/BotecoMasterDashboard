"""Date navigation component for report tabs."""

from __future__ import annotations

from datetime import date, datetime, timedelta

import streamlit as st


def date_nav(
    session_key: str = "report_date",
    label: str = "Select a date",
    help_text: str | None = None,
) -> date:
    """Render date navigation as a single responsive control row."""
    if session_key not in st.session_state:
        st.session_state[session_key] = datetime.now().date()

    selected_date = st.session_state[session_key]
    prev_col, date_col, next_col = st.columns([1.1, 2.4, 1.1])
    with prev_col:
        if st.button("\u2190", key=f"{session_key}_prev", width="stretch"):
            st.session_state[session_key] = selected_date - timedelta(days=1)
    with date_col:
        st.date_input(
            label,
            key=session_key,
            help=help_text,
            format="YYYY-MM-DD",
            label_visibility="collapsed",
            width="stretch",
        )
    with next_col:
        if st.button("\u2192", key=f"{session_key}_next", width="stretch"):
            st.session_state[session_key] = selected_date + timedelta(days=1)

    return st.session_state[session_key]


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
            key=session_key_start,
            format="YYYY-MM-DD",
        )
    with col_end:
        end_date = st.date_input(
            label_end,
            key=session_key_end,
            format="YYYY-MM-DD",
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

    return start_date, end_date
