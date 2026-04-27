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

def kpi_row(
    metrics: List[KpiMetric],
    columns: Optional[int] = None,
) -> None:
    """Render a row of KPI metrics with consistent styling.

    Args:
        metrics: List of KpiMetric dataclasses to render.
        columns: Number of columns. Defaults to len(metrics).
    """
    if not metrics:
        return

    ncols = columns or len(metrics)
    cols = st.columns(ncols)

    for col, metric in zip(cols, metrics, strict=False):
        with col:
            st.metric(
                label=metric.label,
                value=metric.value,
                delta=metric.delta,
                delta_color=metric.delta_color,
                help=metric.help,
            )
