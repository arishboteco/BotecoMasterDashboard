"""Shared UI constants and Plotly defaults for the dashboard."""

import plotly.graph_objects as go
import plotly.io as pio

# ── Brand palette (blue accent) ───────────────────────────────────────────────
BRAND_PRIMARY = "#2563EB"  # Blue — primary actions, links
BRAND_DARK = "#1D4ED8"  # Darker blue — hover/pressed
BRAND_LIGHT = "#3B82F6"  # Lighter blue — gradients
BRAND_SOFT = "#DBEAFE"  # Soft blue tint — backgrounds
BRAND_SUCCESS = "#16A34A"  # Green — positive deltas
BRAND_WARN = "#D97706"  # Amber — warning
BRAND_ERROR = "#DC2626"  # Red — negative deltas, destructive
BRAND_INFO = "#2563EB"  # Blue — info (same as brand)

# ── Surface & neutral palette ─────────────────────────────────────────────────
SURFACE_BASE = "#FFFFFF"  # Main background — pure white
SURFACE_ELEVATED = "#F8FAFC"  # Cards — very light blue-gray
SURFACE_RAISED = "#FFFFFF"  # Modals, tooltips
TEXT_PRIMARY = "#0F172A"  # Primary text — near-black slate
TEXT_SECONDARY = "#475569"  # Secondary text
TEXT_MUTED = "#94A3B8"  # Muted text
BORDER_SUBTLE = "#E2E8F0"  # Light borders
BORDER_MEDIUM = "#CBD5E1"  # Medium borders

# ── Shadow system ─────────────────────────────────────────────────────────────
SHADOW_SM = "0 1px 2px rgba(0,0,0,0.05)"
SHADOW_MD = "0 4px 6px rgba(0,0,0,0.07)"
SHADOW_LG = "0 10px 15px rgba(0,0,0,0.1)"

# ── Border radius system ──────────────────────────────────────────────────────
RADIUS_SM = "6px"
RADIUS_MD = "8px"
RADIUS_LG = "12px"

# ── Chart colorway — blue-forward, colorblind-friendly ────────────────────────
CHART_COLORWAY = [
    "#2563EB",  # blue (primary)
    "#16A34A",  # green
    "#D97706",  # amber
    "#7C3AED",  # violet
    "#0891B2",  # cyan
    "#DC2626",  # red
    "#DB2777",  # pink
    "#475569",  # slate
]

CHART_HEIGHT = 380
CHART_MARGIN = dict(l=48, r=28, t=56, b=48)


def apply_plotly_theme() -> None:
    pio.templates["boteco"] = go.layout.Template(
        layout=dict(
            font=dict(
                family="Inter, DM Sans, sans-serif",
                size=13,
                color=TEXT_PRIMARY,
            ),
            colorway=CHART_COLORWAY,
            hoverlabel=dict(
                bgcolor=SURFACE_RAISED,
                font_size=12,
                bordercolor=BORDER_SUBTLE,
                font_family="Inter, DM Sans, sans-serif",
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
