"""Form-related components for consistent form layouts and confirmations."""

from __future__ import annotations

from typing import Callable, Optional

import streamlit as st


def confirm_dialog(
    message: str,
    confirm_key: str,
    on_confirm: Callable,
    on_cancel: Optional[Callable] = None,
    confirm_label: str = "Yes, delete",
    cancel_label: str = "Cancel",
    confirm_type: str = "primary",
) -> None:
    """Render a two-step confirmation dialog."""
    pending = st.session_state.get(confirm_key)
    if not pending:
        return

    st.error(message)
    dc1, dc2 = st.columns(2)
    with dc1:
        if st.button(confirm_label, key=f"{confirm_key}_yes", type=confirm_type):
            on_confirm()
    with dc2:
        if st.button(cancel_label, key=f"{confirm_key}_no"):
            if on_cancel:
                on_cancel()
            st.session_state.pop(confirm_key, None)
            st.rerun()
