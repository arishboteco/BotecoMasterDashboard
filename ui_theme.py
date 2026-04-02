"""Shared UI constants and Plotly defaults for the dashboard."""

import plotly.graph_objects as go
import plotly.io as pio

# -- Brand palette (Slate & Coral) --------------------------------------------
BRAND_PRIMARY = "#E8734A"  # Coral — primary actions, links
BRAND_DARK = "#D4612E"  # Deep coral — hover/pressed
BRAND_LIGHT = "#F0936E"  # Light coral — gradients
BRAND_SOFT = "#FEF0EB"  # Soft coral tint — backgrounds
BRAND_SUCCESS = "#0D9488"  # Teal — positive deltas
BRAND_WARN = "#D97706"  # Amber — warning
BRAND_ERROR = "#EF4444"  # Red — negative deltas, destructive
BRAND_INFO = "#6366F1"  # Indigo — info

# -- Surface & neutral palette -------------------------------------------------
SURFACE_BASE = "#FFFFFF"  # Main background — white
SURFACE_ELEVATED = "#F8F9FB"  # Cards — very light cool gray
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

# -- Chart colorway — coral-forward, colorblind-friendly ----------------------
CHART_COLORWAY = [
    "#E8734A",  # coral (primary)
    "#0D9488",  # teal
    "#D97706",  # amber
    "#6366F1",  # indigo
    "#EC4899",  # pink
    "#334155",  # slate
    "#8B5CF6",  # violet
    "#059669",  # emerald
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
                bgcolor=SURFACE_RAISED,
                font_size=12,
                bordercolor=BORDER_SUBTLE,
                font_family="DM Sans, sans-serif",
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
