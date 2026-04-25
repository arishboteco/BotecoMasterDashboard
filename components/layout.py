"""Layout components — sections, dividers, containers, and reusable UI blocks."""

from __future__ import annotations

from contextlib import contextmanager
from html import escape
from typing import Generator, Iterable, Optional, Tuple

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


def section_block(
    title: str,
    subtitle: Optional[str] = None,
    icon: str = "widgets",
) -> None:
    """Render a compact section heading block with optional subtitle."""
    subtitle_html = (
        f'<p class="section-block-subtitle">{escape(subtitle)}</p>' if subtitle else ""
    )
    st.markdown(
        f'<div class="section-block">'
        f'<div class="section-block-title">'
        f'<span class="material-symbols-outlined section-block-icon">{escape(icon)}</span>'
        f"<span>{escape(title)}</span>"
        f"</div>"
        f"{subtitle_html}"
        f"</div>",
        unsafe_allow_html=True,
    )


def info_banner(
    message: str,
    tone: str = "info",
    icon: Optional[str] = None,
) -> None:
    """Render a lightweight inline banner for notices and hints."""
    icon_by_tone = {
        "info": "info",
        "success": "check_circle",
        "warning": "warning",
        "error": "error",
        "neutral": "lightbulb",
    }
    safe_tone = tone if tone in icon_by_tone else "info"
    resolved_icon = icon or icon_by_tone[safe_tone]
    st.markdown(
        f'<div class="info-banner info-banner--{safe_tone}">'
        f'<span class="material-symbols-outlined info-banner-icon">{escape(resolved_icon)}</span>'
        f'<span class="info-banner-text">{escape(message)}</span>'
        f"</div>",
        unsafe_allow_html=True,
    )


def filter_strip(
    title: str,
    subtitle: Optional[str] = None,
    icon: str = "tune",
) -> None:
    """Render a compact filter strip header used before filter controls."""
    subtitle_html = (
        f'<span class="filter-strip-subtitle">{escape(subtitle)}</span>'
        if subtitle
        else ""
    )
    st.markdown(
        f'<div class="filter-strip">'
        f'<span class="material-symbols-outlined filter-strip-icon">{escape(icon)}</span>'
        f'<span class="filter-strip-title">{escape(title)}</span>'
        f"{subtitle_html}"
        f"</div>",
        unsafe_allow_html=True,
    )


def primary_action_bar(
    primary_label: str,
    primary_key: str,
    *,
    primary_disabled: bool = False,
    secondary_label: Optional[str] = None,
    secondary_key: Optional[str] = None,
    secondary_type: str = "secondary",
) -> Tuple[bool, bool]:
    """Render a consistent action bar with primary/secondary button hierarchy."""
    if secondary_label and secondary_key:
        c1, c2 = st.columns([1, 4])
        with c1:
            secondary_clicked = st.button(
                secondary_label,
                key=secondary_key,
                type=secondary_type,
                width="stretch",
            )
        with c2:
            primary_clicked = st.button(
                primary_label,
                key=primary_key,
                type="primary",
                disabled=primary_disabled,
                width="stretch",
            )
        return primary_clicked, secondary_clicked

    primary_clicked = st.button(
        primary_label,
        key=primary_key,
        type="primary",
        disabled=primary_disabled,
        width="stretch",
    )
    return primary_clicked, False
