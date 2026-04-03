"""Tests for upload-tab save preparation behavior."""

from pathlib import Path

import customer_report_parser


def _prepare_merged_for_save(merged, location_id, cr_lookup):
    """Inline copy of the upload_tab helper to avoid streamlit import in tests."""
    out = dict(merged)
    out.setdefault("covers", 0)
    out.setdefault("lunch_covers", None)
    out.setdefault("dinner_covers", None)
    return customer_report_parser.apply_covers_overlay(out, location_id, cr_lookup)


class TestPrepareMergedForSave:
    def test_keeps_parser_covers_when_no_overlay(self):
        merged = {
            "date": "2026-03-30",
            "covers": 128,
            "lunch_covers": 54,
            "dinner_covers": 74,
        }

        out = _prepare_merged_for_save(merged, 1, {})

        assert out["covers"] == 128
        assert out["lunch_covers"] == 54
        assert out["dinner_covers"] == 74

    def test_overrides_covers_when_overlay_exists(self):
        merged = {
            "date": "2026-03-30",
            "covers": 128,
            "lunch_covers": None,
            "dinner_covers": None,
        }
        lookup = {
            (1, "2026-03-30"): {
                "covers": 160,
                "lunch_covers": 70,
                "dinner_covers": 90,
            }
        }

        out = _prepare_merged_for_save(merged, 1, lookup)

        assert out["covers"] == 160
        assert out["lunch_covers"] == 70
        assert out["dinner_covers"] == 90


class TestUploadTabSource:
    def test_sync_covers_only_section_removed(self):
        src = Path("tabs/upload_tab.py").read_text(encoding="utf-8")
        assert "### Sync covers only" not in src
