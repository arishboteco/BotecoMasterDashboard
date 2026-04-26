"""Tests for Plotly theme token mappings in ui_theme."""

from __future__ import annotations

import ui_theme


def test_ui_theme_exposes_plotly_chart_token_values() -> None:
    """Ensure chart styling exports stay aligned with design tokens."""
    assert ui_theme.CHART_BG == ui_theme.SURFACE_ELEVATED
    assert ui_theme.CHART_PAPER_BG == ui_theme.SURFACE_ELEVATED
    assert ui_theme.CHART_FONT_COLOR == ui_theme.TEXT_PRIMARY
    assert ui_theme.CHART_GRID_COLOR == ui_theme.BORDER_SUBTLE
    assert ui_theme.CHART_AXIS_COLOR == ui_theme.BORDER_MEDIUM
    assert ui_theme.CHART_TITLE_COLOR == ui_theme.TEXT_PRIMARY
    assert ui_theme.CHART_TICK_COLOR == ui_theme.TEXT_SECONDARY
    assert len(ui_theme.CHART_COLORWAY) >= 5

