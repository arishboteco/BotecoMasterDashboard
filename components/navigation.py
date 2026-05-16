"""Date navigation component for report tabs."""

from __future__ import annotations

from datetime import date, datetime, timedelta

import streamlit as st


def sync_date_from_picker(session_key: str, picker_key: str) -> None:
    """Sync canonical session date from the date_input widget state."""
    if picker_key not in st.session_state:
        return
    st.session_state[session_key] = st.session_state[picker_key]


def shift_date(session_key: str, picker_key: str, days: int) -> None:
    """Move the selected date by the given number of days."""
    next_date = st.session_state[session_key] + timedelta(days=days)
    st.session_state[session_key] = next_date
    st.session_state[picker_key] = next_date


def init_date_state(session_key: str) -> str:
    """Ensure session state is initialised; return the picker key."""
    picker_key = f"{session_key}_picker"
    if session_key not in st.session_state:
        st.session_state[session_key] = datetime.now().date()
    if picker_key not in st.session_state:
        st.session_state[picker_key] = st.session_state[session_key]
    return picker_key


# Keep private aliases so existing internal callers still work.
_sync_session_date_from_picker = sync_date_from_picker
_shift_session_date = shift_date


def date_nav(
    session_key: str = "report_date",
    label: str = "Select a date",
    help_text: str | None = None,
) -> date:
    """Render date navigation as a single responsive control row."""
    picker_key = init_date_state(session_key)
    prev_col, date_col, next_col = st.columns([0.55, 1.5, 0.55])
    with prev_col:
        st.button(
            "\u2190",
            key=f"{session_key}_prev",
            width=44,
            on_click=shift_date,
            args=(session_key, picker_key, -1),
        )
    with next_col:
        st.button(
            "\u2192",
            key=f"{session_key}_next",
            width=44,
            on_click=shift_date,
            args=(session_key, picker_key, 1),
        )
    with date_col:
        st.date_input(
            label,
            key=picker_key,
            help=help_text,
            format="DD-MM-YYYY",
            label_visibility="collapsed",
            on_change=sync_date_from_picker,
            args=(session_key, picker_key),
        )
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
            format="DD-MM-YYYY",
        )
    with col_end:
        end_date = st.date_input(
            label_end,
            key=session_key_end,
            format="DD-MM-YYYY",
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

def sidebar_app_nav(
    items: list[str],
    default: str = "Analytics",
    key: str = "active_app_section",
) -> str:
    """Render global application navigation in the sidebar."""
    if not items:
        return default

    safe_default = default if default in items else items[0]

    if key not in st.session_state or st.session_state[key] not in items:
        st.session_state[key] = safe_default

    for item in items:
        is_active = st.session_state[key] == item
        label = f"▸ {item}" if is_active else item

        clicked = st.sidebar.button(
            label,
            key=f"{key}_{item.lower().replace(' ', '_')}",
            width="stretch",
            type="primary" if is_active else "secondary",
        )

        if clicked and not is_active:
            st.session_state[key] = item
            st.rerun()

    return st.session_state[key]