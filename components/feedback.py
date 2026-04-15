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
