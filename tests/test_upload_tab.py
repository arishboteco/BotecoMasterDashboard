"""Tests for upload tab source-level save flow wiring."""

from pathlib import Path


class TestUploadTabSource:
    def test_sync_covers_only_section_removed(self):
        src = Path("tabs/upload_tab.py").read_text(encoding="utf-8")
        assert "### Sync covers only" not in src

    def test_uses_single_smart_upload_save_path(self):
        src = Path("tabs/upload_tab.py").read_text(encoding="utf-8")
        assert "upload_service.import_upload(" in src
        assert "database.save_daily_summary(" not in src

    def test_does_not_reference_customer_report_parser(self):
        src = Path("tabs/upload_tab.py").read_text(encoding="utf-8")
        assert "customer_report_parser" not in src
