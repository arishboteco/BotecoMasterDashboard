"""Feedback components — toasts, empty states, status messages."""

from __future__ import annotations

from typing import Callable, Literal, Optional

import streamlit as st


def toast(
    message: str,
    kind: Literal["success", "error", "info", "warning"] = "info",
) -> None:
    """Render a toast-style notification."""
    if kind == "success":
        st.success(message)
    elif kind == "error":
        st.error(message)
    elif kind == "warning":
        st.warning(message)
    else:
        st.info(message)


def skeleton_chart() -> None:
    """Render a chart-shaped skeleton placeholder (380px tall)."""
    st.markdown(
        '<div class="skeleton skeleton-chart"></div>', unsafe_allow_html=True
    )


def skeleton_metric_row(count: int = 4) -> None:
    """Render a row of metric-shaped skeleton placeholders."""
    cols = st.columns(count)
    for col in cols:
        with col:
            st.markdown(
                '<div class="skeleton skeleton-metric"></div>',
                unsafe_allow_html=True,
            )


def skeleton_table(rows: int = 5) -> None:
    """Render a skeleton table of `rows` placeholder lines."""
    parts = ''.join(
        '<div class="skeleton skeleton-table-row"></div>' for _ in range(rows)
    )
    st.markdown(parts, unsafe_allow_html=True)


def empty_state(
    message: str,
    hint: Optional[str] = None,
    action_label: Optional[str] = None,
    action_callback: Optional[Callable] = None,
    icon: str = "inbox",
) -> None:
    """Render an empty state with icon, message, optional hint and CTA.

    Args:
        message: Primary empty state message.
        hint: Secondary hint text shown below the message.
        action_label: Label for the CTA button.
        action_callback: Callback invoked when the CTA button is clicked.
        icon: Material Symbols icon name (default: 'inbox').
    """
    hint_html = f'<div class="empty-state-desc">{hint}</div>' if hint else ""
    st.markdown(
        f'<div class="empty-state">'
        f'<span class="empty-state-icon material-symbols-outlined">{icon}</span>'
        f'<div class="empty-state-title">{message}</div>'
        f'{hint_html}'
        f'</div>',
        unsafe_allow_html=True,
    )
    if action_label and action_callback:
        _, btn_col, _ = st.columns([1, 2, 1])
        with btn_col:
            if st.button(action_label, key=f"empty_state_action_{hash(message)}", use_container_width=True):
                action_callback()
