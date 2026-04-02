"""Shared UI constants and Plotly defaults for the dashboard."""

import plotly.graph_objects as go
import plotly.io as pio

# ── Brand palette ─────────────────────────────────────────────────────────────
BRAND_PRIMARY = "#C2703E"   # Warm terracotta — restaurant editorial
BRAND_DARK    = "#A45A2E"   # Hover / pressed state
BRAND_SUCCESS = "#5B7F4A"   # Semantic green — positive deltas, good status
BRAND_WARN    = "#C28B2D"   # Semantic amber — caution / warning
BRAND_ERROR   = "#B84233"   # Semantic red  — negative deltas, destructive

# ── Chart colorway — 8 distinct, colorblind-friendly hues ────────────────────
CHART_COLORWAY = [
    "#C2703E",  # terracotta  (primary)
    "#0369a1",  # steel blue
    "#5B7F4A",  # forest green
    "#7c3aed",  # violet
    "#0891b2",  # cyan / teal
    "#C28B2D",  # warm gold
    "#be185d",  # magenta
    "#475569",  # slate
]

CHART_HEIGHT = 380
CHART_MARGIN = dict(l=48, r=28, t=56, b=48)


def apply_plotly_theme() -> None:
    pio.templates["boteco"] = go.layout.Template(
        layout=dict(
            font=dict(
                family="DM Sans, sans-serif",
                size=13,
                color="#3D2B1F",
            ),
            colorway=CHART_COLORWAY,
            hoverlabel=dict(bgcolor="#FFF8F0", font_size=13),
            margin=CHART_MARGIN,
            title=dict(font=dict(size=16), x=0.02, xanchor="left"),
            plot_bgcolor="#FAF6F1",
            paper_bgcolor="#FFF8F0",
        )
    )
    pio.templates.default = "plotly_white+boteco"
