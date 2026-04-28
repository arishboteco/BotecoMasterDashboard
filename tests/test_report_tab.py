"""Tests for report tab date range wiring."""

from datetime import date
from pathlib import Path

from tabs import report_tab


def test_footfall_metric_ranges_anchor_to_selected_report_date() -> None:
    ranges = report_tab._footfall_metric_ranges(date(2025, 8, 15))

    assert ranges == ("2024-11-01", "2025-07-21", "2025-08-15")


def test_png_preview_grid_does_not_render_redundant_section_headers() -> None:
    src = Path("tabs/report_tab.py").read_text(encoding="utf-8")

    assert "section_title(title, icon=\"image\")" not in src
