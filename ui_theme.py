"""Shared UI constants and Plotly defaults for the dashboard."""

import plotly.graph_objects as go
import plotly.io as pio

# -- Brand palette (Boteco Mango) -----------------------------------------------
BRAND_PRIMARY = "#1F5FA8"  # Deep Royal Blue — primary actions, links
BRAND_DARK = "#174A82"  # Dark blue — hover/pressed
BRAND_LIGHT = "#2A6BB3"  # Lighter blue — gradients
BRAND_SOFT = (
    "#E6F4F3"  # Soft teal tint — backgrounds (teal, not blue, for tropical feel)
)
BRAND_SECONDARY = "#3FA7A3"  # Teal Blue — secondary actions
BRAND_SECONDARY_DARK = "#2F8C89"  # Dark teal — secondary hover
BRAND_SUCCESS = "#3FA7A3"  # Teal — positive deltas (same as BRAND_SECONDARY — distinct semantic roles)
BRAND_WARN = "#F4B400"  # Golden Mustard — warning
BRAND_GREEN = "#6DBE45"  # Leaf Green — freshness, Zomato charts
BRAND_ERROR = "#EF4444"  # Red — negative deltas, destructive
BRAND_INFO = "#6366F1"  # Indigo — info

# -- Surface & neutral palette -------------------------------------------------
SURFACE_BASE = "#F7FAFC"  # Main background — soft off-white
SURFACE_ELEVATED = "#FFFFFF"  # Cards — white
SURFACE_RAISED = "#FFFFFF"  # Modals, tooltips
TEXT_PRIMARY = "#1E293B"  # Primary text — slate 800
TEXT_SECONDARY = "#475569"  # Secondary text — slate 600
TEXT_MUTED = "#94A3B8"  # Muted text — slate 400
BORDER_SUBTLE = "#E2E8F0"  # Light borders — slate 200
BORDER_MEDIUM = "#CBD5E1"  # Medium borders — slate 300

# -- Shadow system -------------------------------------------------------------
SHADOW_SM = "0 1px 2px rgba(0,0,0,0.05)"
SHADOW_MD = "0 4px 6px rgba(0,0,0,0.07)"
SHADOW_LG = "0 10px 15px rgba(0,0,0,0.1)"

# -- Border radius system ------------------------------------------------------
RADIUS_SM = "6px"
RADIUS_MD = "8px"
RADIUS_LG = "12px"

# -- Chart colorway — Boteco Mango brand, 5-color palette ---------------------
CHART_COLORWAY = [
    "#1F5FA8",  # deep royal blue (primary)
    "#3FA7A3",  # teal blue
    "#6DBE45",  # leaf green
    "#F4B400",  # golden mustard
    "#174A82",  # dark blue
]

CHART_HEIGHT = 380
CHART_MARGIN = dict(l=48, r=28, t=56, b=48)


def apply_plotly_theme() -> None:
    pio.templates["boteco"] = go.layout.Template(
        layout=dict(
            font=dict(
                family="Inter, sans-serif",
                size=13,
                color=TEXT_PRIMARY,
            ),
            colorway=CHART_COLORWAY,
            hoverlabel=dict(
                bgcolor=SURFACE_RAISED,
                font_size=12,
                bordercolor=BORDER_SUBTLE,
                font_family="Inter, sans-serif",
            ),
            margin=CHART_MARGIN,
            title=dict(font=dict(size=15, color=TEXT_PRIMARY), x=0.02, xanchor="left"),
            plot_bgcolor=SURFACE_BASE,
            paper_bgcolor=SURFACE_BASE,
            xaxis=dict(
                gridcolor=BORDER_SUBTLE,
                gridwidth=1,
                zerolinecolor=BORDER_MEDIUM,
                title_font=dict(size=12, color=TEXT_SECONDARY),
                tickfont=dict(size=11, color=TEXT_MUTED),
            ),
            yaxis=dict(
                gridcolor=BORDER_SUBTLE,
                gridwidth=1,
                zerolinecolor=BORDER_MEDIUM,
                title_font=dict(size=12, color=TEXT_SECONDARY),
                tickfont=dict(size=11, color=TEXT_MUTED),
            ),
        )
    )
    pio.templates.default = "plotly_white+boteco"
