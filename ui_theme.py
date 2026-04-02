"""Shared UI constants and Plotly defaults for the dashboard."""

import plotly.graph_objects as go
import plotly.io as pio

# ── Brand palette ─────────────────────────────────────────────────────────────
BRAND_PRIMARY = "#C2703E"  # Warm terracotta — restaurant editorial
BRAND_DARK = "#A45A2E"  # Hover / pressed state
BRAND_LIGHT = "#D4895A"  # Lighter variant for gradients
BRAND_SOFT = "#F5EAE0"  # Soft background tint
BRAND_SUCCESS = "#5B7F4A"  # Semantic green — positive deltas, good status
BRAND_WARN = "#C28B2D"  # Semantic amber — caution / warning
BRAND_ERROR = "#B84233"  # Semantic red  — negative deltas, destructive
BRAND_INFO = "#3B82F6"  # Semantic blue — info, links

# ── Surface & neutral palette ─────────────────────────────────────────────────
SURFACE_BASE = "#FAF6F1"  # Main background
SURFACE_ELEVATED = "#FFF8F0"  # Cards, elevated surfaces
SURFACE_RAISED = "#FFFFFF"  # Modals, tooltips
TEXT_PRIMARY = "#3D2B1F"  # Primary text
TEXT_SECONDARY = "#6B5B4E"  # Secondary text (captions, hints)
TEXT_MUTED = "#8C7B6B"  # Muted text
BORDER_SUBTLE = "#E0D5C8"  # Light borders
BORDER_MEDIUM = "#C8B9A8"  # Medium borders

# ── Shadow system ─────────────────────────────────────────────────────────────
SHADOW_SM = "0 1px 3px rgba(60,40,20,0.06)"
SHADOW_MD = "0 4px 12px rgba(60,40,20,0.08)"
SHADOW_LG = "0 8px 24px rgba(60,40,20,0.12)"

# ── Border radius system ──────────────────────────────────────────────────────
RADIUS_SM = "8px"
RADIUS_MD = "12px"
RADIUS_LG = "16px"

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
                color=TEXT_PRIMARY,
            ),
            colorway=CHART_COLORWAY,
            hoverlabel=dict(
                bgcolor=SURFACE_ELEVATED,
                font_size=13,
                bordercolor=BORDER_SUBTLE,
                font_family="DM Sans, sans-serif",
            ),
            margin=CHART_MARGIN,
            title=dict(font=dict(size=16), x=0.02, xanchor="left"),
            plot_bgcolor=SURFACE_BASE,
            paper_bgcolor=SURFACE_ELEVATED,
            xaxis=dict(
                gridcolor=BORDER_SUBTLE,
                gridwidth=0.5,
                zerolinecolor=BORDER_MEDIUM,
            ),
            yaxis=dict(
                gridcolor=BORDER_SUBTLE,
                gridwidth=0.5,
                zerolinecolor=BORDER_MEDIUM,
            ),
        )
    )
    pio.templates.default = "plotly_white+boteco"
