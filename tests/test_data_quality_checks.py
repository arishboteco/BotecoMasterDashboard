"""Tests for services.data_quality.audit_full_history_report — the check battery.

Each check states what it proves and how many days it examined, so these
tests verify both the pass/fail boundary and the days_examined denominator
for every check, plus the AuditReport/MonthHealth roll-ups built on top.
"""

from __future__ import annotations

from services import data_quality


def _patch_audit_sources(
    monkeypatch,
    *,
    earliest_date=None,
    summaries=None,
    categories=None,
    bill_item_days=None,
    payment_method_rows=None,
):
    monkeypatch.setattr("database.get_earliest_date_with_data", lambda location_ids: earliest_date)
    monkeypatch.setattr(
        "database.get_summaries_for_date_range_multi",
        lambda location_ids, start, end: summaries or [],
    )
    monkeypatch.setattr(
        "database_reads.get_category_totals_for_date_range",
        lambda location_ids, start, end: categories or [],
    )
    monkeypatch.setattr(
        "database.get_bill_item_days_for_date_range_multi",
        lambda location_ids, start, end: bill_item_days or [],
    )
    monkeypatch.setattr(
        "database.get_payment_method_sales_for_date_range_multi",
        lambda location_ids, start, end: payment_method_rows or [],
    )


def _check(report, key):
    return next(c for c in report.checks if c.key == key)


def _base_day(**overrides):
    row = {
        "location_id": 1,
        "date": "2026-04-05",
        "net_total": 100000.0,
        "gross_total": 110000.0,
        "my_amount": 101000.0,
        "discount": 1000.0,  # my_amount - discount = 100000 = net_total
        "covers": 40,
        "order_count": 40,
        "cgst": 1500.0,
        "sgst": 1500.0,
        # Payments reconcile against gross_total (tax/service-charge
        # inclusive — what the customer paid), not net_total.
        "cash_sales": 55000.0,
        "card_sales": 55000.0,
        "gpay_sales": 0.0,
        "zomato_sales": 0.0,
        "other_sales": 0.0,
        "upi_sales": 0.0,
        "wallet_sales": 0.0,
        "due_payment_sales": 0.0,
        "bank_transfer_sales": 0.0,
        "boh_sales": 0.0,
        "delivery_sales": 0.0,
        "pickup_sales": 0.0,
        "dine_in_sales": 0.0,
        "menu_qr_sales": 0.0,
        "source_report": "growth_report_day_wise",
    }
    row.update(overrides)
    return row


class TestEmptyAndEdgeCases:
    def test_no_locations_returns_empty_report(self):
        report = data_quality.audit_full_history_report([], {})
        assert report.checks == []
        assert report.locations == []
        assert report.days_audited == 0

    def test_no_earliest_date_does_not_crash(self, monkeypatch):
        _patch_audit_sources(monkeypatch, earliest_date=None)
        report = data_quality.audit_full_history_report(
            [1], {1: "Bagmane"}, as_of_date="2026-04-05"
        )
        assert report.window_start == report.window_end == "2026-04-05"
        assert report.days_audited == 0


class TestCoverageCheck:
    def test_flags_gap_day_and_counts_days_examined(self, monkeypatch):
        _patch_audit_sources(
            monkeypatch,
            earliest_date="2026-04-01",
            summaries=[
                _base_day(date="2026-04-01"),
                _base_day(date="2026-04-03"),
            ],
        )
        report = data_quality.audit_full_history_report(
            [1], {1: "Bagmane"}, as_of_date="2026-04-03"
        )
        check = _check(report, "coverage")
        assert check.severity == "error"
        assert [f.date for f in check.findings] == ["2026-04-02"]
        # Gap check excludes the window's final day (still trading).
        assert check.days_examined == 2  # 04-01, 04-02 only

    def test_no_findings_when_every_day_covered(self, monkeypatch):
        _patch_audit_sources(
            monkeypatch,
            earliest_date="2026-04-01",
            summaries=[_base_day(date="2026-04-01"), _base_day(date="2026-04-02")],
        )
        report = data_quality.audit_full_history_report(
            [1], {1: "Bagmane"}, as_of_date="2026-04-02"
        )
        assert _check(report, "coverage").passed is True


class TestCategoryPresentCheck:
    def test_flags_trading_day_with_no_category_rows(self, monkeypatch):
        _patch_audit_sources(
            monkeypatch,
            earliest_date="2026-04-05",
            summaries=[_base_day(date="2026-04-05")],
            categories=[],
        )
        report = data_quality.audit_full_history_report(
            [1], {1: "Bagmane"}, as_of_date="2026-04-05"
        )
        check = _check(report, "category_present")
        assert check.severity == "error"
        assert len(check.findings) == 1
        assert check.days_examined == 1  # only the one trading day

    def test_zero_sales_day_is_not_examined(self, monkeypatch):
        _patch_audit_sources(
            monkeypatch,
            earliest_date="2026-04-05",
            summaries=[_base_day(date="2026-04-05", net_total=0.0)],
        )
        report = data_quality.audit_full_history_report(
            [1], {1: "Bagmane"}, as_of_date="2026-04-05"
        )
        check = _check(report, "category_present")
        assert check.days_examined == 0
        assert check.findings == []


class TestCategoryReconcilesCheck:
    def test_flags_material_mismatch(self, monkeypatch):
        _patch_audit_sources(
            monkeypatch,
            earliest_date="2026-04-05",
            summaries=[_base_day(date="2026-04-05", net_total=100000.0)],
            categories=[{"location_id": 1, "date": "2026-04-05", "net_amount": 80000.0}],
        )
        report = data_quality.audit_full_history_report(
            [1], {1: "Bagmane"}, as_of_date="2026-04-05"
        )
        check = _check(report, "category_reconciles")
        assert len(check.findings) == 1
        assert check.findings[0].magnitude == 20000.0
        assert check.severity == "warning"

    def test_missing_category_day_is_excluded_not_double_counted(self, monkeypatch):
        # category_present already flags this day; category_reconciles must not.
        _patch_audit_sources(
            monkeypatch,
            earliest_date="2026-04-05",
            summaries=[_base_day(date="2026-04-05")],
            categories=[],
        )
        report = data_quality.audit_full_history_report(
            [1], {1: "Bagmane"}, as_of_date="2026-04-05"
        )
        check = _check(report, "category_reconciles")
        assert check.days_examined == 0
        assert check.findings == []


class TestNetIdentityCheck:
    def test_flags_broken_identity(self, monkeypatch):
        _patch_audit_sources(
            monkeypatch,
            earliest_date="2026-04-05",
            summaries=[
                _base_day(date="2026-04-05", my_amount=101000.0, discount=1000.0, net_total=90000.0)
            ],
        )
        report = data_quality.audit_full_history_report(
            [1], {1: "Bagmane"}, as_of_date="2026-04-05"
        )
        check = _check(report, "net_identity")
        assert check.severity == "error"
        assert len(check.findings) == 1
        assert check.findings[0].magnitude == 10000.0

    def test_legacy_row_with_zero_my_amount_is_skipped(self, monkeypatch):
        _patch_audit_sources(
            monkeypatch,
            earliest_date="2026-04-05",
            summaries=[
                _base_day(
                    date="2026-04-05",
                    my_amount=0.0,
                    discount=500.0,
                    net_total=999999.0,  # would fail the identity if checked
                    source_report="dynamic_report",
                )
            ],
        )
        report = data_quality.audit_full_history_report(
            [1], {1: "Bagmane"}, as_of_date="2026-04-05"
        )
        check = _check(report, "net_identity")
        assert check.days_examined == 0
        assert check.findings == []

    def test_exact_identity_passes(self, monkeypatch):
        _patch_audit_sources(
            monkeypatch,
            earliest_date="2026-04-05",
            summaries=[_base_day(date="2026-04-05")],  # 99000 - (-1000) = 100000 = net_total
        )
        report = data_quality.audit_full_history_report(
            [1], {1: "Bagmane"}, as_of_date="2026-04-05"
        )
        assert _check(report, "net_identity").passed is True


class TestGrossGeNetCheck:
    def test_flags_net_exceeding_gross(self, monkeypatch):
        _patch_audit_sources(
            monkeypatch,
            earliest_date="2026-04-05",
            summaries=[_base_day(date="2026-04-05", net_total=120000.0, gross_total=110000.0)],
        )
        report = data_quality.audit_full_history_report(
            [1], {1: "Bagmane"}, as_of_date="2026-04-05"
        )
        check = _check(report, "gross_ge_net")
        assert len(check.findings) == 1
        assert check.severity == "warning"


class TestNoNegativesCheck:
    def test_flags_negative_field_by_name(self, monkeypatch):
        _patch_audit_sources(
            monkeypatch,
            earliest_date="2026-04-05",
            summaries=[_base_day(date="2026-04-05", card_sales=-500.0)],
        )
        report = data_quality.audit_full_history_report(
            [1], {1: "Bagmane"}, as_of_date="2026-04-05"
        )
        check = _check(report, "no_negatives")
        assert check.severity == "error"
        assert "card_sales" in check.findings[0].detail

    def test_negative_discount_is_flagged(self, monkeypatch):
        _patch_audit_sources(
            monkeypatch,
            earliest_date="2026-04-05",
            summaries=[_base_day(date="2026-04-05", discount=-500.0)],
        )
        report = data_quality.audit_full_history_report(
            [1], {1: "Bagmane"}, as_of_date="2026-04-05"
        )
        check = _check(report, "no_negatives")
        assert len(check.findings) == 1
        assert "discount" in check.findings[0].detail

    def test_clean_day_has_no_negatives_finding(self, monkeypatch):
        _patch_audit_sources(
            monkeypatch,
            earliest_date="2026-04-05",
            summaries=[_base_day(date="2026-04-05")],
        )
        report = data_quality.audit_full_history_report(
            [1], {1: "Bagmane"}, as_of_date="2026-04-05"
        )
        assert _check(report, "no_negatives").passed is True


class TestPaymentsWithinGrossCheck:
    def test_flags_overcounted_standard_payments(self, monkeypatch):
        _patch_audit_sources(
            monkeypatch,
            earliest_date="2026-04-05",
            summaries=[
                _base_day(
                    date="2026-04-05",
                    gross_total=110000.0,
                    cash_sales=90000.0,
                    card_sales=90000.0,  # 180000 total, way over gross
                )
            ],
        )
        report = data_quality.audit_full_history_report(
            [1], {1: "Bagmane"}, as_of_date="2026-04-05"
        )
        check = _check(report, "payments_within_gross")
        assert len(check.findings) == 1

    def test_undercounted_payments_not_flagged(self, monkeypatch):
        # One-sided: dynamic payment types live elsewhere, so an apparent
        # shortfall from standard fields alone must not be flagged.
        _patch_audit_sources(
            monkeypatch,
            earliest_date="2026-04-05",
            summaries=[
                _base_day(
                    date="2026-04-05", gross_total=110000.0, cash_sales=10000.0, card_sales=10000.0
                )
            ],
        )
        report = data_quality.audit_full_history_report(
            [1], {1: "Bagmane"}, as_of_date="2026-04-05"
        )
        assert _check(report, "payments_within_gross").passed is True

    def test_payments_matching_gross_exactly_pass(self, monkeypatch):
        # Verified against production: gross_total == standard + dynamic
        # payments on every saved day, so the default fixture (cash+card =
        # gross_total) must pass cleanly.
        _patch_audit_sources(
            monkeypatch,
            earliest_date="2026-04-05",
            summaries=[
                _base_day(
                    date="2026-04-05",
                    gross_total=110000.0,
                    cash_sales=55000.0,
                    card_sales=55000.0,
                )
            ],
        )
        report = data_quality.audit_full_history_report(
            [1], {1: "Bagmane"}, as_of_date="2026-04-05"
        )
        assert _check(report, "payments_within_gross").passed is True


class TestCoversPresentCheck:
    def test_flags_zero_covers_on_trading_day(self, monkeypatch):
        _patch_audit_sources(
            monkeypatch,
            earliest_date="2026-04-05",
            summaries=[_base_day(date="2026-04-05", covers=0, order_count=0)],
        )
        report = data_quality.audit_full_history_report(
            [1], {1: "Bagmane"}, as_of_date="2026-04-05"
        )
        assert len(_check(report, "covers_present").findings) == 1


class TestServiceSplitCoverageCheck:
    """The check that would have caught the real production incident."""

    def test_flags_category_day_with_no_bill_items(self, monkeypatch):
        _patch_audit_sources(
            monkeypatch,
            earliest_date="2026-04-05",
            summaries=[_base_day(date="2026-04-05")],
            categories=[{"location_id": 1, "date": "2026-04-05", "net_amount": 100000.0}],
            bill_item_days=[],  # no service split saved at all
        )
        report = data_quality.audit_full_history_report(
            [1], {1: "Bagmane"}, as_of_date="2026-04-05"
        )
        check = _check(report, "service_split_coverage")
        assert check.severity == "error"
        assert len(check.findings) == 1
        assert check.days_examined == 1  # only days with category data are checked

    def test_reproduces_the_incident_shape(self, monkeypatch):
        # Item Report covers Apr-May for outlet 2; bill_items only has May.
        # Outlet 1 is fully clean and must not be flagged at all.
        summaries = [
            _base_day(location_id=1, date="2026-05-01"),
            _base_day(location_id=2, date="2026-04-15"),
            _base_day(location_id=2, date="2026-05-01"),
        ]
        categories = [
            {"location_id": 1, "date": "2026-05-01", "net_amount": 100000.0},
            {"location_id": 2, "date": "2026-04-15", "net_amount": 50000.0},
            {"location_id": 2, "date": "2026-05-01", "net_amount": 60000.0},
        ]
        _patch_audit_sources(
            monkeypatch,
            earliest_date="2026-04-15",
            summaries=summaries,
            categories=categories,
            bill_item_days=[
                {"location_id": 1, "date": "2026-05-01"},
                {"location_id": 2, "date": "2026-05-01"},
                # outlet 2, 2026-04-15 has NO bill_items row — the incident.
            ],
        )
        report = data_quality.audit_full_history_report(
            [1, 2], {1: "Indiqube", 2: "Bagmane"}, as_of_date="2026-05-01"
        )
        check = _check(report, "service_split_coverage")
        assert len(check.findings) == 1
        assert check.findings[0].location_id == 2
        assert check.findings[0].date == "2026-04-15"

        by_loc = {loc.location_id: loc for loc in report.locations}
        assert by_loc[1].has_issues is False
        indiqube_service_check = next(
            c for c in by_loc[1].checks if c.key == "service_split_coverage"
        )
        assert indiqube_service_check.findings == []
        bagmane_service_check = next(
            c for c in by_loc[2].checks if c.key == "service_split_coverage"
        )
        assert len(bagmane_service_check.findings) == 1


class TestPaymentReconciliationCheck:
    def test_two_sided_reconciliation_uses_dynamic_payments(self, monkeypatch):
        _patch_audit_sources(
            monkeypatch,
            earliest_date="2026-04-05",
            summaries=[
                _base_day(
                    date="2026-04-05",
                    gross_total=110000.0,
                    cash_sales=45000.0,
                    card_sales=45000.0,
                )
            ],
            payment_method_rows=[{"location_id": 1, "date": "2026-04-05", "amount": 20000.0}],
        )
        report = data_quality.audit_full_history_report(
            [1], {1: "Bagmane"}, as_of_date="2026-04-05"
        )
        # 45000 + 45000 + 20000 = 110000 = gross_total exactly.
        assert _check(report, "payment_reconciliation").passed is True

    def test_flags_real_discrepancy_including_dynamic(self, monkeypatch):
        _patch_audit_sources(
            monkeypatch,
            earliest_date="2026-04-05",
            summaries=[
                _base_day(
                    date="2026-04-05",
                    gross_total=110000.0,
                    cash_sales=40000.0,
                    card_sales=40000.0,
                )
            ],
            payment_method_rows=[{"location_id": 1, "date": "2026-04-05", "amount": 5000.0}],
        )
        report = data_quality.audit_full_history_report(
            [1], {1: "Bagmane"}, as_of_date="2026-04-05"
        )
        # 40000 + 40000 + 5000 = 85000, short of 110000 gross by more than tolerance.
        check = _check(report, "payment_reconciliation")
        assert len(check.findings) == 1


class TestInfoChecks:
    def test_source_uniform_flags_legacy_pipeline(self, monkeypatch):
        _patch_audit_sources(
            monkeypatch,
            earliest_date="2026-04-05",
            summaries=[_base_day(date="2026-04-05", source_report="dynamic_report")],
        )
        report = data_quality.audit_full_history_report(
            [1], {1: "Bagmane"}, as_of_date="2026-04-05"
        )
        check = _check(report, "source_uniform")
        assert check.severity == "info"
        assert len(check.findings) == 1

    def test_info_checks_excluded_from_checks_passed_total(self, monkeypatch):
        _patch_audit_sources(
            monkeypatch,
            earliest_date="2026-04-05",
            summaries=[_base_day(date="2026-04-05", source_report="dynamic_report")],
        )
        report = data_quality.audit_full_history_report(
            [1], {1: "Bagmane"}, as_of_date="2026-04-05"
        )
        info_checks = [c for c in report.checks if c.severity == "info"]
        assert len(info_checks) == 1  # source_uniform
        assert report.checks_total == len(report.checks) - 1


class TestAuditReportRollups:
    def test_days_audited_and_clean_counts(self, monkeypatch):
        _patch_audit_sources(
            monkeypatch,
            earliest_date="2026-04-01",
            summaries=[
                _base_day(date="2026-04-01"),  # clean
                _base_day(date="2026-04-02", covers=0, order_count=0),  # 1 issue
            ],
            categories=[
                {"location_id": 1, "date": "2026-04-01", "net_amount": 100000.0},
                {"location_id": 1, "date": "2026-04-02", "net_amount": 100000.0},
            ],
            bill_item_days=[
                {"location_id": 1, "date": "2026-04-01"},
                {"location_id": 1, "date": "2026-04-02"},
            ],
        )
        report = data_quality.audit_full_history_report(
            [1], {1: "Bagmane"}, as_of_date="2026-04-02"
        )
        assert report.days_audited == 2
        assert report.days_clean == 1
        assert report.days_with_issues == 1

    def test_outlets_clear_counts_only_missing_category_mismatch_gap_signals(self, monkeypatch):
        # outlets_clear is driven by LocationDataQuality.has_issues, which
        # only looks at the three legacy fields (missing/category-missing/
        # mismatch) — an info-only or covers-only finding must not mark an
        # outlet as unclear via this particular property.
        _patch_audit_sources(
            monkeypatch,
            earliest_date="2026-04-05",
            summaries=[_base_day(date="2026-04-05", covers=0, order_count=0)],
            categories=[{"location_id": 1, "date": "2026-04-05", "net_amount": 100000.0}],
            bill_item_days=[{"location_id": 1, "date": "2026-04-05"}],
        )
        report = data_quality.audit_full_history_report(
            [1], {1: "Bagmane"}, as_of_date="2026-04-05"
        )
        assert report.outlets_clear == 1
        assert report.outlet_count == 1
        # But the richer check-based view still shows the covers issue.
        assert _check(report, "covers_present").passed is False


class TestMonthRollup:
    def test_groups_by_month_and_location_newest_first(self, monkeypatch):
        _patch_audit_sources(
            monkeypatch,
            earliest_date="2026-03-01",
            summaries=[
                _base_day(date="2026-03-15"),
                _base_day(date="2026-04-01"),
                _base_day(date="2026-04-02", covers=0, order_count=0),
            ],
            categories=[
                {"location_id": 1, "date": "2026-03-15", "net_amount": 100000.0},
                {"location_id": 1, "date": "2026-04-01", "net_amount": 100000.0},
                {"location_id": 1, "date": "2026-04-02", "net_amount": 100000.0},
            ],
            bill_item_days=[
                {"location_id": 1, "date": "2026-03-15"},
                {"location_id": 1, "date": "2026-04-01"},
                {"location_id": 1, "date": "2026-04-02"},
            ],
        )
        report = data_quality.audit_full_history_report(
            [1], {1: "Bagmane"}, as_of_date="2026-04-02"
        )
        assert [m.month for m in report.months] == ["2026-04", "2026-03"]
        april = report.months[0]
        assert april.days == 2
        assert april.days_clean == 1
        assert april.issue_count == 1
        march = report.months[1]
        assert march.days == 1
        assert march.days_clean == 1
