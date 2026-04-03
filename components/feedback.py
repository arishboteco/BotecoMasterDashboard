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
) -> None:
    """Render an empty state with optional hint and CTA."""
    st.markdown(
        f'<div class="empty-upload-hint">{message}</div>',
        unsafe_allow_html=True,
    )
    if hint:
        st.caption(hint)
    if action_label and action_callback:
        if st.button(action_label, key=f"empty_state_action_{message[:20]}"):
            action_callback()
