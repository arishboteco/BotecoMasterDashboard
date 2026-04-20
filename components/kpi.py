"""KPI metric row component for consistent dashboard metrics."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import streamlit as st


@dataclass
class KpiMetric:
    """Single KPI metric datum."""

    label: str
    value: str
    delta: Optional[str] = None
    delta_color: str = "normal"
    help: Optional[str] = None


_ACCENT_CLASSES = [
    "metric-accent-coral",
    "metric-accent-teal",
    "metric-accent-amber",
    "metric-accent-indigo",
    "metric-accent-slate",
]


def kpi_row(
    metrics: List[KpiMetric],
    columns: Optional[int] = None,
) -> None:
    """Render a row of KPI metrics with consistent styling.

    Each metric is wrapped in a rotating accent class so the colored
    left-border rules in styles._components apply. Order of accents:
    coral → teal → amber → indigo → slate → (cycle).

    Args:
        metrics: List of KpiMetric dataclasses to render.
        columns: Number of columns. Defaults to len(metrics).
    """
    if not metrics:
        return

    ncols = columns or len(metrics)
    cols = st.columns(ncols)

    for i, (col, metric) in enumerate(zip(cols, metrics)):
        accent = _ACCENT_CLASSES[i % len(_ACCENT_CLASSES)]
        with col:
            # Open accent wrapper — closed below. Must be its own markdown
            # call so Streamlit doesn't strip the trailing </div>.
            st.markdown(f'<div class="{accent}">', unsafe_allow_html=True)
            st.metric(
                label=metric.label,
                value=metric.value,
                delta=metric.delta,
                delta_color=metric.delta_color,
                help=metric.help,
            )
            st.markdown("</div>", unsafe_allow_html=True)
