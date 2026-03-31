"""Shared UI constants and Plotly defaults for the dashboard."""

import plotly.graph_objects as go
import plotly.io as pio

BRAND_PRIMARY = "#e94560"
BRAND_SUCCESS = "#4ecca3"
BRAND_WARN = "#ffd93d"
CHART_COLORWAY = [
    BRAND_PRIMARY,
    BRAND_SUCCESS,
    BRAND_WARN,
    "#001f3f",
    "#5f9ea0",
    "#6c757d",
]
CHART_HEIGHT = 380
CHART_MARGIN = dict(l=48, r=28, t=56, b=48)


def apply_plotly_theme() -> None:
    pio.templates["boteco"] = go.layout.Template(
        layout=dict(
            font=dict(
                family="system-ui, 'Segoe UI', sans-serif",
                size=13,
                color="#1a1a1a",
            ),
            colorway=CHART_COLORWAY,
            hoverlabel=dict(bgcolor="white", font_size=13),
            margin=CHART_MARGIN,
            title=dict(font=dict(size=16), x=0.02, xanchor="left"),
            plot_bgcolor="#fafafa",
            paper_bgcolor="#ffffff",
        )
    )
    pio.templates.default = "plotly_white+boteco"
