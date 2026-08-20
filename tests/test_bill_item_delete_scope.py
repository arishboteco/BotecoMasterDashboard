"""Tests for scoping bill_items deletes to the days actually being rewritten.

A Growth Report covering a whole month uploaded alongside an Item Report
covering only part of it used to wipe the Lunch/Dinner split for every day
in the Growth Report, replacing only the days the Item Report covered. The
uncovered days were left with no service data at all.
"""

from __future__ import annotations

from smart_upload import _build_item_report_bill_items_from_services, _dates_locs_for_bill_items


def _services(lunch: float, dinner: float):
    return [{"type": "Lunch", "amount": lunch}, {"type": "Dinner", "amount": dinner}]


class TestDatesLocsForBillItems:
    def test_maps_records_back_to_their_outlet_and_day(self):
        records = _build_item_report_bill_items_from_services(
            2, "2026-08-01", {"services": _services(1000, 2000)}
        )

        assert _dates_locs_for_bill_items(records) == {("2026-08-01", 2)}

    def test_covers_every_outlet_and_day_present(self):
        records = _build_item_report_bill_items_from_services(
            1, "2026-07-15", {"services": _services(500, 900)}
        ) + _build_item_report_bill_items_from_services(
            2, "2026-08-02", {"services": _services(300, 400)}
        )

        assert _dates_locs_for_bill_items(records) == {("2026-07-15", 1), ("2026-08-02", 2)}

    def test_excludes_days_the_item_report_did_not_cover(self):
        # The regression: Growth Report spans July + August for outlet 2, but
        # the Item Report only carries August. July must not be in the delete
        # scope, or its existing service split is destroyed with no replacement.
        growth_dates_locs = {("2026-07-31", 2), ("2026-08-01", 2), ("2026-08-02", 2)}
        records = _build_item_report_bill_items_from_services(
            2, "2026-08-01", {"services": _services(1000, 2000)}
        ) + _build_item_report_bill_items_from_services(
            2, "2026-08-02", {"services": _services(1100, 2100)}
        )

        delete_scope = _dates_locs_for_bill_items(records)

        assert ("2026-07-31", 2) not in delete_scope
        assert delete_scope == {("2026-08-01", 2), ("2026-08-02", 2)}
        assert delete_scope < growth_dates_locs

    def test_ignores_records_without_a_known_outlet(self):
        records = [{"bill_date": "2026-08-01", "restaurant": "Not A Real Outlet"}]

        assert _dates_locs_for_bill_items(records) == set()

    def test_empty_input_yields_empty_scope(self):
        assert _dates_locs_for_bill_items([]) == set()
