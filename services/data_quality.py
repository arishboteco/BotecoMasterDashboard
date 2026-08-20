"""Data-quality audit surfaced on the Upload page.

Growth Report (daily_summary) and Item Report (category_summary) are
uploaded as separate files. When a team member uploads one and forgets
the other — or uploads a file for the wrong outlet/date — the numbers
silently drift apart with no indication in the dashboard. This module
scans a window of saved data per outlet and flags:

  * calendar days with no saved data at all (an upload was skipped)
  * days that have Growth Report sales but no category breakdown
  * days where the category breakdown total materially disagrees with
    the Growth Report's net sales for that day

so the issues can be caught and re-uploaded before they show up as
unexplained gaps in the reports.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Tuple

from core.dates import date_range_inclusive

# A category-total vs net-sales gap below this is normal rounding/allocation
# noise between the two reports and not worth flagging.
MISMATCH_ABS_FLOOR = 25.0
MISMATCH_PCT_FLOOR = 0.01  # 1% of the day's net sales

# How many full prior calendar months (in addition to the current one) the
# Upload page audit looks back over by default. A team's audit of last
# month's numbers often happens after that month has already closed, so
# limiting the check to "this month" would never catch it.
DEFAULT_MONTHS_BACK = 1


@dataclass
class CategoryMismatch:
    date: str
    net_total: float
    category_total: float

    @property
    def diff(self) -> float:
        return self.net_total - self.category_total


@dataclass
class LocationDataQuality:
    location_id: int
    location_name: str
    missing_days: List[str] = field(default_factory=list)
    category_missing_days: List[str] = field(default_factory=list)
    category_mismatches: List[CategoryMismatch] = field(default_factory=list)
    checks: List["IntegrityCheck"] = field(default_factory=list)

    @property
    def has_issues(self) -> bool:
        return bool(self.missing_days or self.category_missing_days or self.category_mismatches)


def _mismatch_tolerance(net_total: float) -> float:
    return max(MISMATCH_ABS_FLOOR, abs(net_total) * MISMATCH_PCT_FLOOR)


def _parse_date(value: Optional[str]) -> date:
    if not value:
        return date.today()
    return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()


def audit_date_range_data_quality(
    location_ids: List[int],
    loc_name_map: Dict[int, str],
    start_date: str,
    end_date: str,
) -> List[LocationDataQuality]:
    """Audit each location's saved data across an explicit inclusive date range.

    Calendar-day gaps are only flagged up to the day before ``end_date``, so
    the most recent (possibly still-trading) day isn't reported as a
    missing upload.
    """
    import database
    from database_reads import get_category_totals_for_date_range

    if not location_ids:
        return []

    start_d = _parse_date(start_date)
    end_d = _parse_date(end_date)
    if end_d < start_d:
        return []

    start_s, end_s = start_d.strftime("%Y-%m-%d"), end_d.strftime("%Y-%m-%d")

    summaries = database.get_summaries_for_date_range_multi(location_ids, start_s, end_s)
    net_by_loc_date: Dict[tuple, float] = {}
    for row in summaries:
        loc_id = row.get("location_id")
        d = str(row.get("date") or "")[:10]
        if loc_id is None or not d:
            continue
        net_by_loc_date[(int(loc_id), d)] = float(row.get("net_total") or 0)

    cat_rows = get_category_totals_for_date_range(location_ids, start_s, end_s)
    cat_by_loc_date: Dict[tuple, float] = {}
    for row in cat_rows or []:
        loc_id = row.get("location_id")
        d = str(row.get("date") or "")[:10]
        if loc_id is None or not d:
            continue
        key = (int(loc_id), d)
        amount = float(row.get("net_amount") or 0)
        cat_by_loc_date[key] = cat_by_loc_date.get(key, 0.0) + amount

    # Exclude the most recent day in the audit window from the gap check —
    # it may still be trading / not yet uploaded.
    gap_end_d = end_d - timedelta(days=1)
    gap_days = (
        list(date_range_inclusive(start_s, gap_end_d.strftime("%Y-%m-%d")))
        if gap_end_d >= start_d
        else []
    )
    all_days = list(date_range_inclusive(start_s, end_s))

    results: List[LocationDataQuality] = []
    for loc_id in location_ids:
        name = loc_name_map.get(loc_id, f"Outlet {loc_id}")
        missing_days = [d for d in gap_days if (loc_id, d) not in net_by_loc_date]

        category_missing_days = []
        category_mismatches = []
        for d in all_days:
            net_total = net_by_loc_date.get((loc_id, d))
            if net_total is None or net_total <= 0:
                continue
            cat_total = cat_by_loc_date.get((loc_id, d))
            if cat_total is None:
                category_missing_days.append(d)
                continue
            if abs(net_total - cat_total) > _mismatch_tolerance(net_total):
                category_mismatches.append(
                    CategoryMismatch(date=d, net_total=net_total, category_total=cat_total)
                )

        results.append(
            LocationDataQuality(
                location_id=loc_id,
                location_name=name,
                missing_days=missing_days,
                category_missing_days=category_missing_days,
                category_mismatches=category_mismatches,
            )
        )

    return results


def audit_month_data_quality(
    location_ids: List[int],
    loc_name_map: Dict[int, str],
    year: int,
    month: int,
    as_of_date: Optional[str] = None,
) -> List[LocationDataQuality]:
    """Audit each location's saved data for a single given month.

    ``as_of_date`` caps the audit window (defaults to today).
    """
    start_d = date(year, month, 1)
    next_month = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    month_end_d = next_month - timedelta(days=1)
    cap_d = _parse_date(as_of_date)
    end_d = min(month_end_d, cap_d)
    if end_d < start_d:
        return []
    return audit_date_range_data_quality(
        location_ids, loc_name_map, start_d.strftime("%Y-%m-%d"), end_d.strftime("%Y-%m-%d")
    )


def audit_recent_data_quality(
    location_ids: List[int],
    loc_name_map: Dict[int, str],
    as_of_date: Optional[str] = None,
    months_back: int = DEFAULT_MONTHS_BACK,
) -> List[LocationDataQuality]:
    """Audit the current month plus ``months_back`` full prior months.

    Unlike :func:`audit_month_data_quality`, this also catches issues in a
    month that has already closed — e.g. discovered during a post-close
    audit — not just problems in the month still in progress.
    """
    cap_d = _parse_date(as_of_date)
    y, m = cap_d.year, cap_d.month
    for _ in range(max(0, months_back)):
        m -= 1
        if m == 0:
            m, y = 12, y - 1
    start_d = date(y, m, 1)
    return audit_date_range_data_quality(
        location_ids, loc_name_map, start_d.strftime("%Y-%m-%d"), cap_d.strftime("%Y-%m-%d")
    )


# ── Check-based integrity audit ─────────────────────────────────────────────
#
# The functions above answer "is there a gap or a mismatch right now". The
# functions below answer a broader question: "prove the saved data is sane",
# by running a fixed battery of checks over the full saved history and
# reporting, for every check, both what it proves and how many days it
# actually examined — so a clean result is demonstrated, not just asserted.

# Standard payment fields Growth Report writes directly onto daily_summary.
# Dynamic payment types (UPI, Swiggy Dineout, Zomato District, ...) are
# written to payment_method_sales instead — see _check_payment_reconciliation.
_STANDARD_PAYMENT_FIELDS = (
    "cash_sales",
    "card_sales",
    "gpay_sales",
    "zomato_sales",
    "other_sales",
    "upi_sales",
    "wallet_sales",
    "due_payment_sales",
    "bank_transfer_sales",
    "boh_sales",
)

# Money/count fields that should never be negative on a saved day.
_NON_NEGATIVE_FIELDS = (
    "net_total",
    "gross_total",
    "discount",
    "cgst",
    "sgst",
    "service_charge",
    "covers",
    "order_count",
    *_STANDARD_PAYMENT_FIELDS,
    "delivery_sales",
    "pickup_sales",
    "dine_in_sales",
    "menu_qr_sales",
)

# Absolute-money tolerance for identity/rounding checks (my_amount - discount
# = net_total, gross >= net). Deliberately tight — these are supposed to be
# exact per the Growth Report's own column formulas, not estimates.
_IDENTITY_TOLERANCE = 1.0


@dataclass
class CheckFinding:
    """One (outlet, date) that failed a specific integrity check."""

    location_id: int
    location_name: str
    date: str
    detail: str
    magnitude: float = 0.0


@dataclass
class IntegrityCheck:
    """One integrity check run across the audited window, pass or fail.

    ``days_examined`` is the denominator — how many (outlet, day) records
    this check actually looked at — so a "0 findings" result reads as
    evidence rather than an unfalsifiable claim.
    """

    key: str
    label: str
    proves: str
    severity: str  # "error" | "warning" | "info"
    days_examined: int
    findings: List[CheckFinding] = field(default_factory=list)
    days_examined_by_loc: Dict[int, int] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return not self.findings

    @property
    def failed_days(self) -> int:
        return len(self.findings)


@dataclass
class MonthHealth:
    """One outlet's data-health summary for one calendar month."""

    month: str  # "YYYY-MM"
    location_id: int
    location_name: str
    days: int
    days_clean: int
    issue_count: int

    @property
    def days_with_issues(self) -> int:
        return self.days - self.days_clean


@dataclass
class AuditReport:
    """Full-history integrity audit: every check, every month, per outlet."""

    window_start: str
    window_end: str
    locations: List[LocationDataQuality] = field(default_factory=list)
    checks: List[IntegrityCheck] = field(default_factory=list)
    months: List[MonthHealth] = field(default_factory=list)
    days_audited: int = 0
    days_clean: int = 0
    # (location_id, date) -> "complete" | "partial" (sales, no category) | "missing".
    # Only covers days from each location's own first saved date onward — the
    # coverage grid's per-day drill-down, computed once here since the checks
    # above already load every row it needs.
    day_status: Dict[Tuple[int, str], str] = field(default_factory=dict)

    @property
    def outlet_count(self) -> int:
        return len(self.locations)

    @property
    def outlets_clear(self) -> int:
        return sum(1 for loc in self.locations if not loc.has_issues)

    @property
    def checks_total(self) -> int:
        return sum(1 for c in self.checks if c.severity != "info")

    @property
    def checks_passed(self) -> int:
        return sum(1 for c in self.checks if c.severity != "info" and c.passed)

    @property
    def days_with_issues(self) -> int:
        return self.days_audited - self.days_clean


@dataclass
class _AuditData:
    """Pre-loaded rows for the window, indexed for the check functions."""

    location_ids: List[int]
    loc_name_map: Dict[int, str]
    all_days: List[str]
    gap_days: List[str]
    rows_by_loc_date: Dict[Tuple[int, str], dict]
    cat_total_by_loc_date: Dict[Tuple[int, str], float]
    bill_item_days: set
    payment_method_sum_by_loc_date: Dict[Tuple[int, str], float]

    def name(self, location_id: int) -> str:
        return self.loc_name_map.get(location_id, f"Outlet {location_id}")

    def earliest_day(self, location_id: int) -> Optional[str]:
        """First saved date for this location, or None if it has no rows at all.

        Outlets don't all start trading on the same day — a location whose
        data begins later than the window's overall start must not have
        every day before it opened reported as a missing upload.
        """
        days = [d for (lid, d) in self.rows_by_loc_date if lid == location_id]
        return min(days) if days else None

    def gap_days_for(self, location_id: int) -> List[str]:
        earliest = self.earliest_day(location_id)
        if earliest is None:
            return list(self.gap_days)
        return [d for d in self.gap_days if d >= earliest]


def _check_coverage(data: _AuditData) -> IntegrityCheck:
    findings: List[CheckFinding] = []
    days_by_loc: Dict[int, int] = {}
    for loc_id in data.location_ids:
        loc_gap_days = data.gap_days_for(loc_id)
        days_by_loc[loc_id] = len(loc_gap_days)
        for d in loc_gap_days:
            if (loc_id, d) not in data.rows_by_loc_date:
                findings.append(
                    CheckFinding(loc_id, data.name(loc_id), d, "No upload found for this date")
                )
    return IntegrityCheck(
        key="coverage",
        label="Daily coverage",
        proves="Every calendar day has saved sales data since the outlet's first upload",
        severity="error",
        days_examined=sum(days_by_loc.values()),
        findings=findings,
        days_examined_by_loc=days_by_loc,
    )


def _check_category_present(data: _AuditData) -> IntegrityCheck:
    findings: List[CheckFinding] = []
    days_by_loc: Dict[int, int] = {}
    for loc_id in data.location_ids:
        checked = 0
        for d in data.all_days:
            row = data.rows_by_loc_date.get((loc_id, d))
            net_total = float(row.get("net_total") or 0) if row else 0.0
            if net_total <= 0:
                continue
            checked += 1
            if (loc_id, d) not in data.cat_total_by_loc_date:
                findings.append(
                    CheckFinding(
                        loc_id,
                        data.name(loc_id),
                        d,
                        "No category breakdown (Item Report not uploaded)",
                    )
                )
        days_by_loc[loc_id] = checked
    return IntegrityCheck(
        key="category_present",
        label="Category breakdown",
        proves="Every trading day has an Item Report category breakdown",
        severity="error",
        days_examined=sum(days_by_loc.values()),
        findings=findings,
        days_examined_by_loc=days_by_loc,
    )


def _check_category_reconciles(data: _AuditData) -> IntegrityCheck:
    findings: List[CheckFinding] = []
    days_by_loc: Dict[int, int] = {}
    for loc_id in data.location_ids:
        checked = 0
        for d in data.all_days:
            row = data.rows_by_loc_date.get((loc_id, d))
            net_total = float(row.get("net_total") or 0) if row else 0.0
            if net_total <= 0:
                continue
            cat_total = data.cat_total_by_loc_date.get((loc_id, d))
            if cat_total is None:
                continue  # already covered by category_present
            checked += 1
            diff = net_total - cat_total
            if abs(diff) > _mismatch_tolerance(net_total):
                findings.append(
                    CheckFinding(
                        loc_id,
                        data.name(loc_id),
                        d,
                        f"Category total ₹{cat_total:,.0f} vs net sales ₹{net_total:,.0f}",
                        abs(diff),
                    )
                )
        days_by_loc[loc_id] = checked
    return IntegrityCheck(
        key="category_reconciles",
        label="Category reconciliation",
        proves="Category totals sum to net sales (within tolerance)",
        severity="warning",
        days_examined=sum(days_by_loc.values()),
        findings=findings,
        days_examined_by_loc=days_by_loc,
    )


def _check_net_identity(data: _AuditData) -> IntegrityCheck:
    findings: List[CheckFinding] = []
    days_by_loc: Dict[int, int] = {}
    for loc_id in data.location_ids:
        checked = 0
        for d in data.all_days:
            row = data.rows_by_loc_date.get((loc_id, d))
            if not row:
                continue
            my_amount = float(row.get("my_amount") or 0)
            if my_amount == 0:
                continue  # legacy-flow row — my_amount is never populated
            checked += 1
            discount = float(row.get("discount") or 0)
            net_total = float(row.get("net_total") or 0)
            expected = my_amount - discount
            diff = expected - net_total
            if abs(diff) > _IDENTITY_TOLERANCE:
                findings.append(
                    CheckFinding(
                        loc_id,
                        data.name(loc_id),
                        d,
                        f"My Amount ₹{my_amount:,.0f} − Discount ₹{discount:,.0f} "
                        f"= ₹{expected:,.0f}, but Net Sales is ₹{net_total:,.0f}",
                        abs(diff),
                    )
                )
        days_by_loc[loc_id] = checked
    return IntegrityCheck(
        key="net_identity",
        label="Net sales identity",
        proves="My Amount minus Discount equals Net Sales",
        severity="error",
        days_examined=sum(days_by_loc.values()),
        findings=findings,
        days_examined_by_loc=days_by_loc,
    )


def _check_gross_ge_net(data: _AuditData) -> IntegrityCheck:
    findings: List[CheckFinding] = []
    days_by_loc: Dict[int, int] = {}
    for loc_id in data.location_ids:
        checked = 0
        for d in data.all_days:
            row = data.rows_by_loc_date.get((loc_id, d))
            if not row:
                continue
            net_total = float(row.get("net_total") or 0)
            gross_total = float(row.get("gross_total") or 0)
            if net_total <= 0 and gross_total <= 0:
                continue
            checked += 1
            diff = net_total - gross_total
            if diff > _IDENTITY_TOLERANCE:
                findings.append(
                    CheckFinding(
                        loc_id,
                        data.name(loc_id),
                        d,
                        f"Net sales ₹{net_total:,.0f} exceeds gross total ₹{gross_total:,.0f}",
                        diff,
                    )
                )
        days_by_loc[loc_id] = checked
    return IntegrityCheck(
        key="gross_ge_net",
        label="Gross ≥ net",
        proves="No day has net sales exceeding its gross total",
        severity="warning",
        days_examined=sum(days_by_loc.values()),
        findings=findings,
        days_examined_by_loc=days_by_loc,
    )


def _check_no_negatives(data: _AuditData) -> IntegrityCheck:
    findings: List[CheckFinding] = []
    days_by_loc: Dict[int, int] = {}
    for loc_id in data.location_ids:
        checked = 0
        for d in data.all_days:
            row = data.rows_by_loc_date.get((loc_id, d))
            if not row:
                continue
            checked += 1
            negative_fields = [f for f in _NON_NEGATIVE_FIELDS if float(row.get(f) or 0) < -0.01]
            if negative_fields:
                findings.append(
                    CheckFinding(
                        loc_id,
                        data.name(loc_id),
                        d,
                        "Negative value(s): " + ", ".join(negative_fields),
                        float(len(negative_fields)),
                    )
                )
        days_by_loc[loc_id] = checked
    return IntegrityCheck(
        key="no_negatives",
        label="No negative amounts",
        proves="No sales, tax, or payment field is negative",
        severity="error",
        days_examined=sum(days_by_loc.values()),
        findings=findings,
        days_examined_by_loc=days_by_loc,
    )


def _check_payments_within_gross(data: _AuditData) -> IntegrityCheck:
    """One-sided pre-check using only fields already loaded on daily_summary.

    Payment amounts (cash/card/gpay/...) are what the customer actually
    paid — tax- and service-charge-inclusive — so they reconcile against
    ``gross_total``, not ``net_total`` (net sales is pre-tax, pre-service
    revenue). Verified against production data: gross_total exactly equals
    standard-field payments plus payment_method_sales' dynamic types on
    every saved day (0 mismatches across 306 days).

    Dynamic payment types live in payment_method_sales (see
    ``_check_payment_reconciliation`` for the two-sided version), so a
    two-sided comparison here would false-positive whenever a day has any
    dynamic payment channel. Over-counting from the standard fields alone,
    against gross, is unambiguous though.
    """
    findings: List[CheckFinding] = []
    days_by_loc: Dict[int, int] = {}
    for loc_id in data.location_ids:
        checked = 0
        for d in data.all_days:
            row = data.rows_by_loc_date.get((loc_id, d))
            gross_total = float(row.get("gross_total") or 0) if row else 0.0
            if gross_total <= 0:
                continue
            checked += 1
            payment_sum = sum(float(row.get(f) or 0) for f in _STANDARD_PAYMENT_FIELDS)
            diff = payment_sum - gross_total
            if diff > _mismatch_tolerance(gross_total):
                findings.append(
                    CheckFinding(
                        loc_id,
                        data.name(loc_id),
                        d,
                        f"Recorded payments ₹{payment_sum:,.0f} exceed gross total "
                        f"₹{gross_total:,.0f}",
                        diff,
                    )
                )
        days_by_loc[loc_id] = checked
    return IntegrityCheck(
        key="payments_within_gross",
        label="Payments within gross",
        proves="Standard payment fields never exceed the day's gross total",
        severity="warning",
        days_examined=sum(days_by_loc.values()),
        findings=findings,
        days_examined_by_loc=days_by_loc,
    )


def _check_covers_present(data: _AuditData) -> IntegrityCheck:
    findings: List[CheckFinding] = []
    days_by_loc: Dict[int, int] = {}
    for loc_id in data.location_ids:
        checked = 0
        for d in data.all_days:
            row = data.rows_by_loc_date.get((loc_id, d))
            net_total = float(row.get("net_total") or 0) if row else 0.0
            if net_total <= 0:
                continue
            checked += 1
            covers = int(row.get("covers") or 0)
            order_count = int(row.get("order_count") or 0)
            if covers <= 0 or order_count <= 0:
                findings.append(
                    CheckFinding(
                        loc_id,
                        data.name(loc_id),
                        d,
                        f"Covers {covers}, orders {order_count}",
                    )
                )
        days_by_loc[loc_id] = checked
    return IntegrityCheck(
        key="covers_present",
        label="Covers recorded",
        proves="Trading days have covers and order counts recorded",
        severity="warning",
        days_examined=sum(days_by_loc.values()),
        findings=findings,
        days_examined_by_loc=days_by_loc,
    )


def _check_service_split_coverage(data: _AuditData) -> IntegrityCheck:
    """Catches an Item Report spanning more days than its Growth Report.

    This is the check that would have caught a real production incident:
    an Item Report covering months the Growth Report didn't produced
    category data with no Lunch/Dinner service split at all on the extra
    days, and nothing surfaced it until a manual audit weeks later.
    """
    findings: List[CheckFinding] = []
    days_by_loc: Dict[int, int] = {}
    for loc_id in data.location_ids:
        checked = 0
        for d in data.all_days:
            if (loc_id, d) not in data.cat_total_by_loc_date:
                continue  # only meaningful on days that have category data
            checked += 1
            if (loc_id, d) not in data.bill_item_days:
                findings.append(
                    CheckFinding(
                        loc_id,
                        data.name(loc_id),
                        d,
                        "Category data exists but no Lunch/Dinner service split was saved",
                    )
                )
        days_by_loc[loc_id] = checked
    return IntegrityCheck(
        key="service_split_coverage",
        label="Service split coverage",
        proves="Every day with a category breakdown also has a Lunch/Dinner split",
        severity="error",
        days_examined=sum(days_by_loc.values()),
        findings=findings,
        days_examined_by_loc=days_by_loc,
    )


def _check_payment_reconciliation(data: _AuditData) -> IntegrityCheck:
    """Two-sided reconciliation: standard + dynamic payments vs gross total.

    Payments reconcile against ``gross_total`` (tax- and service-charge-
    inclusive — what the customer actually paid), not ``net_total``.
    Verified against production data: this identity holds exactly on every
    one of 306 saved days, so with both payment sources loaded this is a
    near-exact check, not an estimate.
    """
    findings: List[CheckFinding] = []
    days_by_loc: Dict[int, int] = {}
    for loc_id in data.location_ids:
        checked = 0
        for d in data.all_days:
            row = data.rows_by_loc_date.get((loc_id, d))
            gross_total = float(row.get("gross_total") or 0) if row else 0.0
            if gross_total <= 0:
                continue
            standard = sum(float(row.get(f) or 0) for f in _STANDARD_PAYMENT_FIELDS) if row else 0.0
            dynamic = data.payment_method_sum_by_loc_date.get((loc_id, d), 0.0)
            if not dynamic and standard == 0:
                continue  # no payment data loaded for this day at all — nothing to check
            checked += 1
            total = standard + dynamic
            diff = total - gross_total
            if abs(diff) > _mismatch_tolerance(gross_total):
                findings.append(
                    CheckFinding(
                        loc_id,
                        data.name(loc_id),
                        d,
                        f"Payments total ₹{total:,.0f} vs gross total ₹{gross_total:,.0f}",
                        abs(diff),
                    )
                )
        days_by_loc[loc_id] = checked
    return IntegrityCheck(
        key="payment_reconciliation",
        label="Payment reconciliation",
        proves="Recorded payments (standard + dynamic) equal the gross total charged",
        severity="warning",
        days_examined=sum(days_by_loc.values()),
        findings=findings,
        days_examined_by_loc=days_by_loc,
    )


def _check_source_uniform(data: _AuditData) -> IntegrityCheck:
    """Informational: flags days saved via a legacy import pipeline."""
    findings: List[CheckFinding] = []
    days_by_loc: Dict[int, int] = {}
    for loc_id in data.location_ids:
        checked = 0
        for d in data.all_days:
            row = data.rows_by_loc_date.get((loc_id, d))
            net_total = float(row.get("net_total") or 0) if row else 0.0
            if net_total <= 0:
                continue
            checked += 1
            source_report = str(row.get("source_report") or "")
            if source_report and source_report != "growth_report_day_wise":
                findings.append(
                    CheckFinding(
                        loc_id,
                        data.name(loc_id),
                        d,
                        f"Saved via legacy pipeline ({source_report})",
                    )
                )
        days_by_loc[loc_id] = checked
    return IntegrityCheck(
        key="source_uniform",
        label="Single pipeline",
        proves="All days were saved by the current Growth Report importer",
        severity="info",
        days_examined=sum(days_by_loc.values()),
        findings=findings,
        days_examined_by_loc=days_by_loc,
    )


_ALL_CHECKS = (
    _check_coverage,
    _check_category_present,
    _check_category_reconciles,
    _check_net_identity,
    _check_gross_ge_net,
    _check_no_negatives,
    _check_payments_within_gross,
    _check_covers_present,
    _check_service_split_coverage,
    _check_payment_reconciliation,
    _check_source_uniform,
)


def _filter_check_for_location(check: IntegrityCheck, location_id: int) -> IntegrityCheck:
    return IntegrityCheck(
        key=check.key,
        label=check.label,
        proves=check.proves,
        severity=check.severity,
        days_examined=check.days_examined_by_loc.get(location_id, 0),
        findings=[f for f in check.findings if f.location_id == location_id],
        days_examined_by_loc={location_id: check.days_examined_by_loc.get(location_id, 0)},
    )


def _location_legacy_fields(
    data: _AuditData, loc_id: int
) -> Tuple[List[str], List[str], List[CategoryMismatch]]:
    """Reproduce the original three-field summary from the same loaded data."""
    missing_days = [
        d for d in data.gap_days_for(loc_id) if (loc_id, d) not in data.rows_by_loc_date
    ]
    category_missing_days: List[str] = []
    category_mismatches: List[CategoryMismatch] = []
    for d in data.all_days:
        row = data.rows_by_loc_date.get((loc_id, d))
        net_total = float(row.get("net_total") or 0) if row else 0.0
        if net_total <= 0:
            continue
        cat_total = data.cat_total_by_loc_date.get((loc_id, d))
        if cat_total is None:
            category_missing_days.append(d)
            continue
        if abs(net_total - cat_total) > _mismatch_tolerance(net_total):
            category_mismatches.append(
                CategoryMismatch(date=d, net_total=net_total, category_total=cat_total)
            )
    return missing_days, category_missing_days, category_mismatches


def _build_month_rollup(
    data: _AuditData, issues_by_loc_date: Dict[Tuple[int, str], int]
) -> List[MonthHealth]:
    buckets: Dict[Tuple[str, int], Dict[str, int]] = {}
    for (loc_id, d), _row in data.rows_by_loc_date.items():
        month = d[:7]
        key = (month, loc_id)
        bucket = buckets.setdefault(key, {"days": 0, "clean": 0, "issues": 0})
        bucket["days"] += 1
        day_issues = issues_by_loc_date.get((loc_id, d), 0)
        if day_issues == 0:
            bucket["clean"] += 1
        else:
            bucket["issues"] += day_issues

    months = [
        MonthHealth(
            month=month,
            location_id=loc_id,
            location_name=data.name(loc_id),
            days=bucket["days"],
            days_clean=bucket["clean"],
            issue_count=bucket["issues"],
        )
        for (month, loc_id), bucket in buckets.items()
    ]
    # Stable sort: location_name ascending within each month, months newest first.
    months.sort(key=lambda m: m.location_name)
    months.sort(key=lambda m: m.month, reverse=True)
    return months


def audit_full_history_report(
    location_ids: List[int],
    loc_name_map: Dict[int, str],
    as_of_date: Optional[str] = None,
) -> AuditReport:
    """Run the full integrity check battery over every saved day.

    Unlike the ``audit_*_data_quality`` functions above (which flag gaps and
    mismatches for a fixed recent window), this proves the whole saved
    history is sane: every check states what it proves and how many days it
    examined, and a per-month roll-up shows whether any past month has
    quietly rotted.
    """
    import database
    from database_reads import get_category_totals_for_date_range

    if not location_ids:
        return AuditReport(window_start="", window_end="")

    cap_d = _parse_date(as_of_date)
    earliest = database.get_earliest_date_with_data(location_ids)
    start_d = _parse_date(earliest) if earliest else cap_d
    end_d = cap_d
    if end_d < start_d:
        start_d = end_d

    start_s, end_s = start_d.strftime("%Y-%m-%d"), end_d.strftime("%Y-%m-%d")

    summaries = database.get_summaries_for_date_range_multi(location_ids, start_s, end_s)
    rows_by_loc_date: Dict[Tuple[int, str], dict] = {}
    for row in summaries:
        loc_id = row.get("location_id")
        d = str(row.get("date") or "")[:10]
        if loc_id is None or not d:
            continue
        rows_by_loc_date[(int(loc_id), d)] = row

    cat_rows = get_category_totals_for_date_range(location_ids, start_s, end_s)
    cat_total_by_loc_date: Dict[Tuple[int, str], float] = {}
    for row in cat_rows or []:
        loc_id = row.get("location_id")
        d = str(row.get("date") or "")[:10]
        if loc_id is None or not d:
            continue
        key = (int(loc_id), d)
        amount = float(row.get("net_amount") or 0)
        cat_total_by_loc_date[key] = cat_total_by_loc_date.get(key, 0.0) + amount

    bill_item_rows = database.get_bill_item_days_for_date_range_multi(location_ids, start_s, end_s)
    bill_item_days = {(int(r["location_id"]), r["date"]) for r in bill_item_rows}

    pm_rows = database.get_payment_method_sales_for_date_range_multi(location_ids, start_s, end_s)
    payment_method_sum: Dict[Tuple[int, str], float] = {}
    for row in pm_rows or []:
        loc_id = row.get("location_id")
        d = str(row.get("date") or "")[:10]
        if loc_id is None or not d:
            continue
        key = (int(loc_id), d)
        payment_method_sum[key] = payment_method_sum.get(key, 0.0) + float(row.get("amount") or 0)

    gap_end_d = end_d - timedelta(days=1)
    gap_days = (
        list(date_range_inclusive(start_s, gap_end_d.strftime("%Y-%m-%d")))
        if gap_end_d >= start_d
        else []
    )
    all_days = list(date_range_inclusive(start_s, end_s))

    data = _AuditData(
        location_ids=location_ids,
        loc_name_map=loc_name_map,
        all_days=all_days,
        gap_days=gap_days,
        rows_by_loc_date=rows_by_loc_date,
        cat_total_by_loc_date=cat_total_by_loc_date,
        bill_item_days=bill_item_days,
        payment_method_sum_by_loc_date=payment_method_sum,
    )

    checks = [check_fn(data) for check_fn in _ALL_CHECKS]

    issues_by_loc_date: Dict[Tuple[int, str], int] = {}
    for check in checks:
        if check.severity == "info":
            continue
        for f in check.findings:
            key = (f.location_id, f.date)
            issues_by_loc_date[key] = issues_by_loc_date.get(key, 0) + 1

    days_audited = len(rows_by_loc_date)
    days_clean = sum(1 for key in rows_by_loc_date if issues_by_loc_date.get(key, 0) == 0)
    months = _build_month_rollup(data, issues_by_loc_date)

    day_status: Dict[Tuple[int, str], str] = {}
    for loc_id in location_ids:
        earliest = data.earliest_day(loc_id)
        if earliest is None:
            continue
        for d in all_days:
            if d < earliest:
                continue
            row = rows_by_loc_date.get((loc_id, d))
            if row is None:
                day_status[(loc_id, d)] = "missing"
                continue
            net_total = float(row.get("net_total") or 0)
            if net_total <= 0 or (loc_id, d) in cat_total_by_loc_date:
                day_status[(loc_id, d)] = "complete"
            else:
                day_status[(loc_id, d)] = "partial"

    locations: List[LocationDataQuality] = []
    for loc_id in location_ids:
        missing_days, category_missing_days, category_mismatches = _location_legacy_fields(
            data, loc_id
        )
        loc_checks = [_filter_check_for_location(c, loc_id) for c in checks]
        locations.append(
            LocationDataQuality(
                location_id=loc_id,
                location_name=data.name(loc_id),
                missing_days=missing_days,
                category_missing_days=category_missing_days,
                category_mismatches=category_mismatches,
                checks=loc_checks,
            )
        )

    return AuditReport(
        window_start=start_s,
        window_end=end_s,
        locations=locations,
        checks=checks,
        months=months,
        days_audited=days_audited,
        days_clean=days_clean,
        day_status=day_status,
    )
