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
    )
    if picked != selected_date:
        st.session_state[session_key] = picked
        st.rerun()

    return selected_date
