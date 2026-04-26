"""Shared UI constants and Plotly defaults for the dashboard."""

from __future__ import annotations

import plotly.graph_objects as go
import plotly.io as pio

from styles import _tokens

# -- Semantic token aliases -----------------------------------------------------
PRIMARY = _tokens.PRIMARY
SURFACE = _tokens.SURFACE
SURFACE_ELEVATED = _tokens.SURFACE_ELEVATED
TEXT = _tokens.TEXT
BORDER = _tokens.BORDER
SUCCESS = _tokens.SUCCESS
ERROR = _tokens.ERROR

# -- Backward-compatible names used across existing modules --------------------
BRAND_PRIMARY = PRIMARY
BRAND_DARK = _tokens.PRIMARY_DARK
BRAND_LIGHT = _tokens.PRIMARY_LIGHT
BRAND_SOFT = _tokens.PRIMARY_SOFT
BRAND_SECONDARY = "#3FA7A3"
BRAND_SUCCESS = BRAND_SECONDARY
BRAND_WARN = "#F4B400"
BRAND_GREEN = "#6DBE45"
BRAND_ERROR = "#EF4444"
BRAND_INFO = "#6366F1"

ACHIEVEMENT_HIGH_BG = "#DCFCE7"
ACHIEVEMENT_HIGH_TEXT = "#166534"
ACHIEVEMENT_MED_BG = "#FEF9C3"
ACHIEVEMENT_MED_TEXT = "#854D0E"
ACHIEVEMENT_LOW_BG = "#FEE2E2"
ACHIEVEMENT_LOW_TEXT = "#991B1B"

CHART_MA_ACCENT = "#FF6B35"
CHART_POSITIVE = "#22C55E"
CHART_NEGATIVE = BRAND_ERROR
CHART_NEUTRAL = BRAND_INFO
CHART_BAR_MUTED = _tokens.BORDER_STRONG

SURFACE_BASE = SURFACE
SURFACE_RAISED = _tokens.SURFACE_RAISED
TEXT_PRIMARY = TEXT
TEXT_SECONDARY = _tokens.TEXT_SECONDARY
TEXT_MUTED = _tokens.TEXT_MUTED
BORDER_SUBTLE = BORDER
BORDER_MEDIUM = _tokens.BORDER_MEDIUM

SHADOW_SM = "0 1px 2px rgba(0,0,0,0.05)"

CHART_COLORWAY = [
    _tokens.PRIMARY,
    _tokens.PRIMARY_DARK,
    _tokens.PRIMARY_LIGHT,
    _tokens.SUCCESS,
    _tokens.BORDER_STRONG,
    _tokens.ERROR,
]

CHART_BG = _tokens.SURFACE_ELEVATED
CHART_PAPER_BG = _tokens.SURFACE_ELEVATED
CHART_FONT_COLOR = _tokens.TEXT
CHART_GRID_COLOR = _tokens.BORDER
CHART_AXIS_COLOR = _tokens.BORDER_MEDIUM
CHART_TITLE_COLOR = _tokens.TEXT
CHART_TICK_COLOR = _tokens.TEXT_SECONDARY

CHART_HEIGHT = 380
CHART_MARGIN = dict(l=48, r=28, t=56, b=48)

MSG_SUCCESS = SUCCESS
MSG_WARNING = "#B45309"
MSG_ERROR = ERROR


def apply_plotly_theme() -> None:
    """Register the `boteco` Plotly template and set it as default."""
    pio.templates["boteco"] = go.layout.Template(
        layout=dict(
            font=dict(
                family="Inter, sans-serif",
                size=13,
                color=CHART_FONT_COLOR,
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
            hoverlabel=dict(
                bgcolor=SURFACE_ELEVATED,
                font_size=12,
                bordercolor=BORDER,
                font_family="Inter, sans-serif",
                font_color=TEXT,
                align="left",
                namelength=-1,
            ),
            title=dict(font=dict(size=15, color=CHART_TITLE_COLOR), x=0.02, xanchor="left"),
            plot_bgcolor=CHART_BG,
            paper_bgcolor=CHART_PAPER_BG,
            xaxis=dict(
                gridcolor=CHART_GRID_COLOR,
                gridwidth=1,
                linecolor=CHART_AXIS_COLOR,
                zerolinecolor=CHART_AXIS_COLOR,
                title_font=dict(size=12, color=TEXT_SECONDARY),
                tickfont=dict(size=11, color=CHART_TICK_COLOR),
            ),
            yaxis=dict(
                gridcolor=CHART_GRID_COLOR,
                gridwidth=1,
                linecolor=CHART_AXIS_COLOR,
                zerolinecolor=CHART_AXIS_COLOR,
                title_font=dict(size=12, color=TEXT_SECONDARY),
                tickfont=dict(size=11, color=CHART_TICK_COLOR),
                tickformat=",",
            ),
        )
    )
    pio.templates.default = "plotly_white+boteco"
