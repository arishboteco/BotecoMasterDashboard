"""Source-level tests for footfall tab bulk paste UI wiring."""

from pathlib import Path


def test_bulk_paste_ui_controls_present() -> None:
    src = Path("tabs/footfall_tab.py").read_text(encoding="utf-8")
    assert "Bulk paste overrides" in src
    assert "Preview parsed rows" in src
    assert "Apply bulk upload" in src


def test_bulk_paste_copy_mentions_skip_existing_behavior() -> None:
    src = Path("tabs/footfall_tab.py").read_text(encoding="utf-8")
    assert "existing override dates are skipped" in src
