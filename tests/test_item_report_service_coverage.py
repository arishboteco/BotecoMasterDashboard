"""Service splits must follow the Item Report's dates, not the Growth Report's.

Regression: an Item Report covering Jun–Aug uploaded alongside a Growth
Report covering only Aug produced categories for all three months but a
Lunch/Dinner split for August alone. Service rows were emitted from the
per-day loop, which only iterates days the Growth Report supplied.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import smart_upload
from smart_upload import _dates_locs_for_bill_items, _dedupe_bill_items
from uploads.models import DayResult


def _services(lunch=1000.0, dinner=2000.0):
    return [{"type": "Lunch", "amount": lunch}, {"type": "Dinner", "amount": dinner}]


class _Recorder:
    """Captures what save_smart_upload_results would write to Supabase."""

    def __init__(self):
        self.saved_bill_items = []
        self.deleted_pairs = set()
        self.saved_categories = []


@pytest.fixture
def recorder(monkeypatch):
    """Patch database_writes — save_smart_upload_results imports it internally."""
    import database_writes

    rec = _Recorder()

    def _save_bill_items(_client, records):
        rec.saved_bill_items.extend(records)

    def _delete_bill_items(_client, pairs):
        rec.deleted_pairs |= set(pairs)

    def _save_categories(_client, records):
        rec.saved_categories.extend(records)

    monkeypatch.setattr(database_writes, "save_bill_items", _save_bill_items)
    monkeypatch.setattr(database_writes, "delete_bill_items_by_dates_locs", _delete_bill_items)
    monkeypatch.setattr(database_writes, "save_category_summary_batch", _save_categories)
    monkeypatch.setattr(database_writes, "delete_category_summary_batch", lambda *a, **k: None)
    monkeypatch.setattr(
        database_writes, "upsert_daily_summaries_supabase_batch", lambda *a, **k: None
    )
    monkeypatch.setattr(database_writes, "save_upload_records_batch", lambda *a, **k: None)
    monkeypatch.setattr(database_writes, "delete_payment_method_sales_batch", lambda *a, **k: None)
    monkeypatch.setattr(database_writes, "save_payment_method_sales_batch", lambda *a, **k: None)
    return rec


def _bagmane_result():
    """Bagmane's actual shape: Item Report Jun-Aug, Growth Report Aug only."""
    return SimpleNamespace(
        files=[],
        global_notes=[],
        # The Growth Report supplied only August, so only August has day rows.
        location_results={
            2: [
                DayResult(
                    date="2026-08-01",
                    merged={"date": "2026-08-01", "net_total": 5000.0, "covers": 10},
                    source_kinds=["growth_report_day_wise"],
                )
            ]
        },
        category_by_loc={
            2: [
                {"date": d, "category_name": "Food", "net_amount": 100.0}
                for d in ("2026-06-15", "2026-07-15", "2026-08-01")
            ]
        },
        item_service_by_loc={
            2: {
                "2026-06-15": _services(),
                "2026-07-15": _services(),
                "2026-08-01": _services(),
            }
        },
        item_payment_split_by_loc={},
        new_flow_meta={},
    )


class TestServiceRowsFollowItemReportDates:
    def test_service_rows_cover_every_item_report_day(self, monkeypatch, recorder):
        monkeypatch.setattr(smart_upload.database, "use_supabase", lambda: True)
        monkeypatch.setattr(smart_upload.database, "get_supabase_client", lambda: object())

        smart_upload.save_smart_upload_results(_bagmane_result(), location_id=2, uploaded_by="test")

        covered = {r["bill_date"] for r in recorder.saved_bill_items}
        # June and July are the regression: previously only August survived.
        assert covered == {"2026-06-15", "2026-07-15", "2026-08-01"}

    def test_lunch_and_dinner_both_emitted_per_day(self, monkeypatch, recorder):
        monkeypatch.setattr(smart_upload.database, "use_supabase", lambda: True)
        monkeypatch.setattr(smart_upload.database, "get_supabase_client", lambda: object())

        smart_upload.save_smart_upload_results(_bagmane_result(), location_id=2, uploaded_by="test")

        july = [r for r in recorder.saved_bill_items if r["bill_date"] == "2026-07-15"]
        assert {r["item_name"] for r in july} == {"Lunch Bucket", "Dinner Bucket"}
        assert sum(r["net_amount"] for r in july) == 3000.0

    def test_delete_scope_matches_the_days_being_written(self, monkeypatch, recorder):
        monkeypatch.setattr(smart_upload.database, "use_supabase", lambda: True)
        monkeypatch.setattr(smart_upload.database, "get_supabase_client", lambda: object())

        smart_upload.save_smart_upload_results(_bagmane_result(), location_id=2, uploaded_by="test")

        assert recorder.deleted_pairs == {
            ("2026-06-15", 2),
            ("2026-07-15", 2),
            ("2026-08-01", 2),
        }


class TestDedupeBillItems:
    def test_drops_repeats_of_the_same_bucket(self):
        records = smart_upload._build_item_report_bill_items_from_services(
            2, "2026-07-15", {"services": _services()}
        )

        assert len(_dedupe_bill_items(records + list(records))) == len(records)

    def test_keeps_distinct_days_and_outlets(self):
        records = smart_upload._build_item_report_bill_items_from_services(
            2, "2026-07-15", {"services": _services()}
        ) + smart_upload._build_item_report_bill_items_from_services(
            1, "2026-07-15", {"services": _services()}
        )

        deduped = _dedupe_bill_items(records)

        assert len(deduped) == 4
        assert _dates_locs_for_bill_items(deduped) == {("2026-07-15", 1), ("2026-07-15", 2)}
