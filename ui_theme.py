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

# -- Conditional formatting colors for tables --------------------------------
TABLE_ACHIEVEMENT_GREEN = "#10B981"  # ≥100% achievement
TABLE_ACHIEVEMENT_YELLOW = "#FBBF24"  # 70–99% achievement
TABLE_ACHIEVEMENT_RED = "#EF4444"  # <70% achievement

# -- Achievement % cell styles (bg + text pairs for Styler.map) --------------
# Light bg + dark text pairs; contrast is intrinsic to the cell, readable on
# any surrounding surface.
ACHIEVEMENT_HIGH_BG = "#DCFCE7"
ACHIEVEMENT_HIGH_TEXT = "#166534"
ACHIEVEMENT_MED_BG = "#FEF9C3"
ACHIEVEMENT_MED_TEXT = "#854D0E"
ACHIEVEMENT_LOW_BG = "#FEE2E2"
ACHIEVEMENT_LOW_TEXT = "#991B1B"

# -- Chart semantic accents (distinct from brand palette for visual punch) ---
CHART_MA_ACCENT = "#FF6B35"  # Moving-average overlay line (orange)
CHART_POSITIVE = "#22C55E"  # Best-performer bar (bright green)
CHART_NEGATIVE = "#EF4444"  # Worst-performer bar (red)
CHART_NEUTRAL = "#6366F1"  # Neutral bar (indigo)
CHART_BAR_MUTED = "#94A3B8"  # De-emphasized bar (slate 400) for non-highlight rows

# -- Surface & neutral palette -------------------------------------------------
SURFACE_BASE = "#F7FAFC"  # Main background — soft off-white
SURFACE_ELEVATED = "#FFFFFF"  # Cards — white
SURFACE_RAISED = "#FFFFFF"  # Modals, tooltips
TEXT_PRIMARY = "#1E293B"  # Primary text — slate 800
TEXT_SECONDARY = "#475569"  # Secondary text — slate 600
TEXT_MUTED = "#475569"  # Muted text — slate 600 (WCAG AA compliant, was 500 which failed)
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
CHART_HEIGHT_MOBILE = 280  # Used via responsive CSS override + autosize=True
CHART_MARGIN = dict(l=48, r=28, t=56, b=48)

# -- Dark mode surface tokens (used by boteco-dark Plotly template) -----------
SURFACE_BASE_DARK = "#0F172A"  # slate 900
SURFACE_ELEVATED_DARK = "#1E293B"  # slate 800
SURFACE_RAISED_DARK = "#334155"  # slate 700
TEXT_PRIMARY_DARK = "#F1F5F9"  # slate 100
TEXT_SECONDARY_DARK = "#CBD5E1"  # slate 300
TEXT_MUTED_DARK = "#94A3B8"  # slate 400
BORDER_SUBTLE_DARK = "#334155"  # slate 700
BORDER_MEDIUM_DARK = "#475569"  # slate 600

# -- Message text colors for iframe toolbar (distinct from button-flash accents) --
# Chosen for readability on surrounding surface (not for brand punch).
MSG_SUCCESS_LIGHT = "#15803D"  # matches --success-text in light
MSG_WARNING_LIGHT = "#B45309"  # matches --warning-text equivalent (amber-700)
MSG_ERROR_LIGHT = "#B91C1C"  # matches --error-text in light
MSG_SUCCESS_DARK = "#86EFAC"  # green (matches --success-text in dark)
MSG_WARNING_DARK = "#FBBF24"  # amber (matches --accent-amber in dark)
MSG_ERROR_DARK = "#FCA5A5"  # red (matches --error-text in dark)

# -- Shared hovertemplate fragments -------------------------------------------
# Bold metric value + de-emphasized label. `%{` placeholders are escaped for f-strings.
HOVERTEMPLATE_SALES = "<b>₹%{y:,.0f}</b><br><span style='color:#475569'>%{x}</span><extra></extra>"
HOVERTEMPLATE_APC = "<b>₹%{y:,.1f}</b><br><span style='color:#475569'>%{x}</span><extra></extra>"
HOVERTEMPLATE_COUNT = "<b>%{y:,d}</b><br><span style='color:#475569'>%{x}</span><extra></extra>"


def apply_plotly_theme() -> None:
    """Register `boteco` (light) and `boteco-dark` templates; set `boteco` as default."""
    # Shared layout properties across light/dark variants
    _shared_layout = dict(
        font=dict(
            family="Inter, sans-serif",
            size=13,
        ),
        colorway=CHART_COLORWAY,
        margin=CHART_MARGIN,
        autosize=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.25,
            xanchor="center",
            x=0.5,
            bgcolor="rgba(0,0,0,0)",
            bordercolor="rgba(0,0,0,0)",
            font=dict(size=11, family="Inter, sans-serif"),
        ),
    )

    # ── Light template (boteco) ──────────────────────────────
    pio.templates["boteco"] = go.layout.Template(
        layout=dict(
            **_shared_layout,
            hoverlabel=dict(
                bgcolor=SURFACE_ELEVATED,
                font_size=12,
                bordercolor=BORDER_SUBTLE,
                font_family="Inter, sans-serif",
                font_color=TEXT_PRIMARY,
                align="left",
                namelength=-1,
            ),
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
                tickformat=",",  # thousand separator by default
            ),
        )
    )

    # ── Dark template (boteco-dark) ──────────────────────────
    pio.templates["boteco-dark"] = go.layout.Template(
        layout=dict(
            **_shared_layout,
            hoverlabel=dict(
                bgcolor=SURFACE_RAISED_DARK,
                font_size=12,
                bordercolor=BORDER_SUBTLE_DARK,
                font_family="Inter, sans-serif",
                font_color=TEXT_PRIMARY_DARK,
                align="left",
                namelength=-1,
            ),
            title=dict(
                font=dict(size=15, color=TEXT_PRIMARY_DARK), x=0.02, xanchor="left"
            ),
            plot_bgcolor=SURFACE_BASE_DARK,
            paper_bgcolor=SURFACE_BASE_DARK,
            xaxis=dict(
                gridcolor=BORDER_SUBTLE_DARK,
                gridwidth=1,
                zerolinecolor=BORDER_MEDIUM_DARK,
                title_font=dict(size=12, color=TEXT_SECONDARY_DARK),
                tickfont=dict(size=11, color=TEXT_MUTED_DARK),
            ),
            yaxis=dict(
                gridcolor=BORDER_SUBTLE_DARK,
                gridwidth=1,
                zerolinecolor=BORDER_MEDIUM_DARK,
                title_font=dict(size=12, color=TEXT_SECONDARY_DARK),
                tickfont=dict(size=11, color=TEXT_MUTED_DARK),
                tickformat=",",
            ),
        )
    )

    pio.templates.default = "plotly_white+boteco"


def plotly_template_for_theme(theme: str = "light") -> str:
    """Return the Plotly template chain string for the given UI theme."""
    if theme == "dark":
        return "plotly_dark+boteco-dark"
    return "plotly_white+boteco"
