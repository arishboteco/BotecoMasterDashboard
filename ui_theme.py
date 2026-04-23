"""Shared UI constants and Plotly defaults for the dashboard."""

import plotly.graph_objects as go
import plotly.io as pio

# -- Brand palette (Boteco Mango — logo-derived) ---------------------------
# Primary:   #005AAB — Royal Blue
# Secondary: #A2D06E — Lime Green (success)
# Accent:    #FDB813 — Golden Yellow (accent/warning)
# Tertiary:  #54C5D0 — Sky Teal

BRAND_PRIMARY = "#005AAB"
BRAND_DARK = "#004080"
BRAND_LIGHT = "#2D7AC9"
BRAND_SOFT = "#EBF4FF"
BRAND_SECONDARY = "#54C5D0"
BRAND_SECONDARY_DARK = "#3BA8B5"
BRAND_SUCCESS = "#A2D06E"
BRAND_WARN = "#FDB813"
BRAND_GREEN = "#A2D06E"
BRAND_ERROR = "#EF4444"
BRAND_INFO = "#6366F1"

# -- Conditional formatting colors for tables --------------------------------
TABLE_ACHIEVEMENT_GREEN = "#10B981"  # ≥100% achievement
TABLE_ACHIEVEMENT_YELLOW = "#FBBF24"  # 70–99% achievement
TABLE_ACHIEVEMENT_RED = "#EF4444"  # <70% achievement

# -- Surface & neutral palette -------------------------------------------------
SURFACE_BASE = "#F7FAFC"
SURFACE_ELEVATED = "#FFFFFF"
SURFACE_RAISED = "#FFFFFF"
TEXT_PRIMARY = "#1E293B"
TEXT_SECONDARY = "#475569"
TEXT_MUTED = "#64748B"
BORDER_SUBTLE = "#E2E8F0"
BORDER_MEDIUM = "#CBD5E1"

# -- Shadow system -------------------------------------------------------------
SHADOW_SM = "0 1px 2px rgba(0,0,0,0.05)"
SHADOW_MD = "0 4px 6px rgba(0,0,0,0.07)"
SHADOW_LG = "0 10px 15px rgba(0,0,0,0.1)"

# -- Border radius system ------------------------------------------------------
RADIUS_SM = "6px"
RADIUS_MD = "8px"
RADIUS_LG = "12px"

# -- Chart colorway — logo palette, 5-color -----------------------------------
CHART_COLORWAY = [
    "#005AAB",  # royal blue (primary)
    "#54C5D0",  # sky teal
    "#A2D06E",  # lime green
    "#FDB813",  # golden yellow
    "#2D7AC9",  # bright blue
]

CHART_HEIGHT = 380
CHART_HEIGHT_MOBILE = 280  # Used via responsive CSS override + autosize=True
CHART_MARGIN = dict(l=48, r=28, t=56, b=48)

# -- Dark mode surface tokens --------------------------------------------------
SURFACE_BASE_DARK = "#0F172A"
SURFACE_ELEVATED_DARK = "#1E293B"
SURFACE_RAISED_DARK = "#334155"
TEXT_PRIMARY_DARK = "#F1F5F9"
TEXT_SECONDARY_DARK = "#CBD5E1"
TEXT_MUTED_DARK = "#94A3B8"
BORDER_SUBTLE_DARK = "#334155"
BORDER_MEDIUM_DARK = "#475569"

# -- Dark mode chart colorway --------------------------------------------------
CHART_COLORWAY_DARK = [
    "#2D7AC9",  # bright blue
    "#7DD3E0",  # bright teal
    "#A2D06E",  # lime green (same — already bright)
    "#FBBF24",  # bright amber
    "#5A97D6",  # light blue
]

# -- Dark mode message colors for iframe toolbar ---------------------------------
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
    _dark_layout = dict(_shared_layout, colorway=CHART_COLORWAY_DARK)
    pio.templates["boteco-dark"] = go.layout.Template(
        layout=dict(
            **_dark_layout,
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
