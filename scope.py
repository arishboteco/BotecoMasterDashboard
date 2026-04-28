"""Multi-location report scope: aggregate daily summaries for combined views."""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

import config
import database
import pos_parser as parser
import utils


def _normalize_detail_lists(summary: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(summary or {})

    cats = []
    for c in out.get("categories") or []:
        cats.append(
            {
                "category": c.get("category") or "Other",
                "qty": int(c.get("qty") or 0),
                "amount": float(c.get("amount") or c.get("total") or 0),
            }
        )
    if cats or out.get("categories") is not None:
        out["categories"] = cats

    svcs = []
    for s in out.get("services") or []:
        svcs.append(
            {
                "type": s.get("type") or s.get("service_type") or "",
                "amount": float(s.get("amount") or s.get("total") or 0),
            }
        )
    if svcs or out.get("services") is not None:
        out["services"] = svcs

    return out


def sum_location_monthly_targets(location_ids: List[int]) -> float:
    total = 0.0
    for lid in location_ids:
        s = database.get_location_settings(lid)
        if s:
            total += float(s.get("target_monthly_sales") or 0)
    return total if total > 0 else float(config.MONTHLY_TARGET)


def sum_location_seat_counts(location_ids: List[int]) -> int:
    n = 0
    for lid in location_ids:
        s = database.get_location_settings(lid)
        if s and s.get("seat_count"):
            n += int(s["seat_count"])
    return n


def aggregate_daily_summaries(
    summaries: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Merge multiple DB summary dicts (same calendar date, different locations)."""
    summaries = [s for s in summaries if s]
    if not summaries:
        return None
    if len(summaries) == 1:
        return _normalize_detail_lists(summaries[0])

    summaries = [_normalize_detail_lists(s) for s in summaries]

    numeric_keys = (
        "covers",
        "gross_total",
        "net_total",
        "cash_sales",
        "card_sales",
        "gpay_sales",
        "zomato_sales",
        "other_sales",
        "service_charge",
        "cgst",
        "sgst",
        "discount",
        "complimentary",
        "target",
    )
    first = summaries[0]
    out: Dict[str, Any] = {"date": first.get("date")}
    for k in numeric_keys:
        out[k] = sum(float(s.get(k) or 0) for s in summaries)

    lc_sum = 0
    dc_sum = 0
    lc_any = False
    dc_any = False
    for s in summaries:
        lc = s.get("lunch_covers")
        if lc is not None and not (isinstance(lc, float) and math.isnan(lc)):
            lc_sum += int(lc or 0)
            lc_any = True
        dc = s.get("dinner_covers")
        if dc is not None and not (isinstance(dc, float) and math.isnan(dc)):
            dc_sum += int(dc or 0)
            dc_any = True
    out["lunch_covers"] = lc_sum if lc_any else None
    out["dinner_covers"] = dc_sum if dc_any else None

    cats: Dict[str, Dict[str, Any]] = {}
    for s in summaries:
        for c in s.get("categories") or []:
            k = c.get("category") or "Other"
            if k not in cats:
                cats[k] = {"qty": 0, "amount": 0.0}
            cats[k]["qty"] += int(c.get("qty", 0))
            cats[k]["amount"] += float(c.get("amount", 0))
    out["categories"] = [
        {"category": k, "qty": int(v["qty"]), "amount": v["amount"]}
        for k, v in sorted(cats.items(), key=lambda x: -x[1]["amount"])
    ]

    svc_amt: Dict[str, float] = defaultdict(float)
    for s in summaries:
        for sv in s.get("services") or []:
            key = str(sv.get("type") or sv.get("service_type") or "")
            svc_amt[key] += float(sv.get("amount", 0) or 0)
    out["services"] = [
        {"type": k, "amount": v} for k, v in sorted(svc_amt.items(), key=lambda x: -x[1]) if v > 0
    ]

    out.pop("id", None)
    tgt = float(out.get("target") or 0)
    net = float(out.get("net_total") or 0)
    cov = int(out.get("covers") or 0)
    out["pct_target"] = round((net / tgt) * 100, 2) if tgt > 0 else 0.0
    out["apc"] = (net / cov) if cov > 0 and net > 0 else 0.0
    out["turns"] = None
    return out


def get_daily_summary_for_scope(location_ids: List[int], date_str: str) -> Optional[Dict[str, Any]]:
    if not location_ids:
        return None
    rows = database.get_summaries_for_date_range_multi(location_ids, date_str, date_str)
    parts = [r for r in rows if r.get("date") == date_str]
    return aggregate_daily_summaries(parts)


def _synthetic_daily_summary(location_id: int, date_str: str) -> Dict[str, Any]:
    """Zero-filled day row plus location targets when no DB row exists for that date."""
    st = database.get_location_settings(location_id)
    monthly = (
        float(st["target_monthly_sales"])
        if st and st.get("target_monthly_sales")
        else float(config.MONTHLY_TARGET)
    )
    recent = database.get_recent_summaries(location_id, weeks=8)
    weekday_mix = utils.compute_weekday_mix(recent)
    day_targets = utils.compute_day_targets(monthly, weekday_mix)
    day_target = utils.get_target_for_date(day_targets, date_str)

    return {
        "date": date_str,
        "location_id": location_id,
        "covers": 0,
        "gross_total": 0.0,
        "net_total": 0.0,
        "cash_sales": 0.0,
        "gpay_sales": 0.0,
        "zomato_sales": 0.0,
        "card_sales": 0.0,
        "other_sales": 0.0,
        "service_charge": 0.0,
        "cgst": 0.0,
        "sgst": 0.0,
        "discount": 0.0,
        "complimentary": 0.0,
        "target": day_target,
        "categories": [],
        "services": [],
        "lunch_covers": None,
        "dinner_covers": None,
    }


def get_daily_report_bundle(
    location_ids: List[int], date_str: str
) -> Tuple[List[Tuple[int, str, Dict[str, Any]]], Optional[Dict[str, Any]]]:
    """
    Per-outlet enriched summaries (including zero-filled days) and optional combined.

    Returns ([(id, name, enriched), ...], combined_enriched_or_None).
    If no location has data for the date, combined is None and the first list is empty.
    """
    if not location_ids:
        return [], None

    rows = database.get_summaries_for_date_range_multi(location_ids, date_str, date_str)
    rows_by_loc: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
    for r in rows:
        rows_by_loc[r["location_id"]].append(r)

    outlets: List[Tuple[int, str, Dict[str, Any]]] = []
    parts_raw: List[Dict[str, Any]] = []

    for lid in location_ids:
        st = database.get_location_settings(lid)
        name = str(st["name"]) if st and st.get("name") else str(lid)
        monthly_tgt = (
            float(st["target_monthly_sales"])
            if st and st.get("target_monthly_sales")
            else float(config.MONTHLY_TARGET)
        )
        loc_rows = rows_by_loc.get(lid, [])
        if loc_rows:
            base = dict(loc_rows[0])
            detailed = database.get_daily_summary(lid, date_str) or {}
            if detailed.get("categories") is not None:
                base["categories"] = list(detailed.get("categories") or [])
            if detailed.get("services") is not None:
                base["services"] = list(detailed.get("services") or [])
            parts_raw.append(base)
        else:
            base = _synthetic_daily_summary(lid, date_str)
        enriched = enrich_summary_for_display(base, [lid], monthly_tgt, date_str)
        outlets.append((lid, name, enriched))

    if not parts_raw:
        return [], None

    combined = aggregate_daily_summaries(parts_raw)
    if combined is None:
        return [], None
    monthly_all = sum_location_monthly_targets(location_ids)
    combined_e = enrich_summary_for_display(combined, location_ids, monthly_all, date_str)
    return outlets, combined_e


def merge_month_footfall_rows(
    location_ids: List[int], year: int, month: int
) -> List[Dict[str, Any]]:
    by_date: Dict[str, Dict[str, Any]] = defaultdict(
        lambda: {"covers": 0, "lunch_covers": 0, "dinner_covers": 0, "has_split": False}
    )
    for row in database.get_summaries_for_month_multi(location_ids, year, month):
        d = str(row.get("date", ""))[:10]
        b = by_date[d]
        b["covers"] += int(row.get("covers") or 0)
        if row.get("lunch_covers") is not None or row.get("dinner_covers") is not None:
            b["has_split"] = True
            b["lunch_covers"] += int(row.get("lunch_covers") or 0)
            b["dinner_covers"] += int(row.get("dinner_covers") or 0)
    out: List[Dict[str, Any]] = []
    for d in sorted(by_date.keys()):
        b = by_date[d]
        r: Dict[str, Any] = {"date": d, "covers": b["covers"]}
        if b["has_split"]:
            r["lunch_covers"] = b["lunch_covers"]
            r["dinner_covers"] = b["dinner_covers"]
        else:
            r["lunch_covers"] = None
            r["dinner_covers"] = None
        out.append(r)
    return out


def merge_summaries_by_date(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Combine rows from multiple locations that share a date (for analytics charts)."""
    by_date: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for r in rows:
        d = str(r.get("date", ""))[:10]
        by_date[d].append(r)
    merged: List[Dict[str, Any]] = []
    for d in sorted(by_date.keys()):
        agg = aggregate_daily_summaries(by_date[d])
        if agg:
            merged.append(agg)
    return merged


def enrich_summary_for_display(
    summary: Dict[str, Any],
    location_ids: List[int],
    monthly_target: float,
    date_str: str,
) -> Dict[str, Any]:
    """Attach MTD and derived metrics for single or combined scope."""
    y = int(date_str[0:4])
    m = int(date_str[5:7])
    seats = sum_location_seat_counts(location_ids)
    if seats > 0:
        summary = dict(summary)
        summary["seat_count"] = seats
    mtd = parser.calculate_mtd_metrics_multi(
        location_ids, monthly_target, year=y, month=m, as_of_date=date_str
    )
    summary = dict(summary)
    summary.update(mtd)
    summary = parser.calculate_derived_metrics(summary)
    summary.pop("seat_count", None)
    return summary
