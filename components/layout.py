"""Layout components — sections, dividers, containers."""

from __future__ import annotations

from contextlib import contextmanager
from html import escape
from typing import Generator, Iterable, Optional

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


def page_header(
    title: str,
    subtitle: str,
    context: Optional[str] = None,
) -> None:
    """Render a consistent page hero block."""
    context_html = ""
    if context:
        context_html = f'<span class="page-hero-context">{escape(context)}</span>'
    st.markdown(
        f'<section class="page-hero">'
        f'<div class="page-hero-content">'
        f'<p class="page-hero-kicker">Operations</p>'
        f'<h2 class="page-hero-title">{escape(title)}</h2>'
        f'<p class="page-hero-subtitle">{escape(subtitle)}</p>'
        f'</div>{context_html}</section>',
        unsafe_allow_html=True,
    )


def workflow_steps(steps: Iterable[str], active_index: int = 0) -> None:
    """Render lightweight workflow chips for linear tasks."""
    pills = []
    for idx, text in enumerate(steps):
        state = "workflow-step"
        if idx == active_index:
            state += " active"
        pills.append(f'<span class="{state}">{idx + 1}. {escape(text)}</span>')
    st.markdown(
        f'<div class="workflow-steps">{"".join(pills)}</div>',
        unsafe_allow_html=True,
    )
