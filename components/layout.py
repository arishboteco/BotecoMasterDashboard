"""Layout components — sections, dividers, containers."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Generator, Optional

import streamlit as st


@contextmanager
def section(
    title: str,
    caption: Optional[str] = None,
    border: bool = True,
) -> Generator[None, None, None]:
    """Render a section container with title and optional caption."""
    st.markdown(f"### {title}")
    if caption:
        st.caption(caption)
    if border:
        with st.container(border=True):
            yield
    else:
        yield


def divider(style: str = "gradient") -> None:
    """Render a visual divider."""
    if style == "gradient":
        st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
    else:
        st.markdown("---")
