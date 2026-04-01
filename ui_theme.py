"""Shared UI constants and Plotly defaults for the dashboard."""

import plotly.graph_objects as go
import plotly.io as pio

BRAND_PRIMARY = "#C2703E"
BRAND_SUCCESS = "#5B7F4A"
BRAND_WARN = "#C28B2D"
CHART_COLORWAY = [
    BRAND_PRIMARY,
    BRAND_SUCCESS,
    "#8B6343",
    "#C4A55A",
    "#B07D8A",
    "#5E7E8A",
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
