"""Regression coverage for report date navigation control styling."""

from __future__ import annotations

from styles import _components


def test_report_date_nav_control_bar_selectors_and_touch_targets_present() -> None:
    """Control bar CSS must keep scoped selectors and >=44px button touch target."""
    css = _components.COMPACT_KPIS_FOR_REPORT_TAB

    required_fragments = [
        ".report-filter-shell {",
        '.report-filter-shell [data-testid="stHorizontalBlock"]',
        '.report-filter-shell [data-testid="stButton"] > button',
        '.report-filter-shell [data-testid="stButton"] > button:hover',
        '.report-filter-shell [data-testid="stButton"] > button:focus-visible',
        '.report-filter-shell [data-testid="stDateInput"] input',
        '.report-filter-shell [data-testid="stDateInput"] input:focus',
        "@media (max-width: 900px)",
    ]

    for fragment in required_fragments:
        assert fragment in css

    assert "width: 44px" in css or "min-width: 44px" in css
    assert "height: 44px" in css or "min-height: 44px" in css
