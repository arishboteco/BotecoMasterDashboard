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
from typing import Dict, List, Optional

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
