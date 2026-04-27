"""Apply manual footfall overrides on top of POS-derived daily summaries.

Overrides live in the `footfall_overrides` table and are intentionally kept
separate from `daily_summaries` so they survive POS re-uploads. This module
is the single place reads consult to overlay overrides and inject synthetic
rows for dates where only an override exists.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Tuple

from repositories.footfall_override_repository import (
    FootfallOverrideRepository,
    get_footfall_override_repository,
)

# Key the synthetic-row marker so consumers can distinguish them if needed
# (for example to render with a different style).
OVERRIDE_ONLY_FLAG = "_override_only"


def _synthetic_summary(
    location_id: int,
    date: str,
    override: Dict[str, Any],
) -> Dict[str, Any]:
    """Construct a zero-filled summary dict for a date that has only an override."""
    lunch = override.get("lunch_covers")
    dinner = override.get("dinner_covers")
    covers = (int(lunch) if lunch is not None else 0) + (
        int(dinner) if dinner is not None else 0
    )
    return {
        "location_id": location_id,
        "date": date,
        "covers": covers,
        "lunch_covers": int(lunch) if lunch is not None else None,
        "dinner_covers": int(dinner) if dinner is not None else None,
        "gross_total": 0.0,
        "net_total": 0.0,
        "cash_sales": 0.0,
        "card_sales": 0.0,
        "gpay_sales": 0.0,
        "zomato_sales": 0.0,
        "other_sales": 0.0,
        "service_charge": 0.0,
        "cgst": 0.0,
        "sgst": 0.0,
        "discount": 0.0,
        "complimentary": 0.0,
        "apc": 0.0,
        "turns": 0.0,
        "categories": [],
        "services": [],
        OVERRIDE_ONLY_FLAG: True,
    }


def _overlay(summary: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """Return a copy of `summary` with override values applied per-leg."""
    out = dict(summary)
    lunch_o = override.get("lunch_covers")
    dinner_o = override.get("dinner_covers")
    if lunch_o is not None:
        out["lunch_covers"] = int(lunch_o)
    if dinner_o is not None:
        out["dinner_covers"] = int(dinner_o)

    # Whenever any override leg is in play, recompute total covers from the
    # current legs (override leg + POS leg fall-through).
    if lunch_o is not None or dinner_o is not None:
        lc = out.get("lunch_covers")
        dc = out.get("dinner_covers")
        out["covers"] = (int(lc) if lc is not None else 0) + (
            int(dc) if dc is not None else 0
        )
        # Recompute APC if we have net_total — keeps the report KPI consistent.
        net = float(out.get("net_total") or 0)
        cov = int(out.get("covers") or 0)
        if cov > 0 and net > 0:
            out["apc"] = net / cov
        else:
            out["apc"] = 0.0
    return out


def _date_str(value: Any) -> str:
    """Normalize a summary's `date` value to a YYYY-MM-DD string."""
    if value is None:
        return ""
    s = str(value)
    return s[:10]


def apply_overrides(
    summaries: List[Dict[str, Any]],
    location_ids: Iterable[int],
    start_date: str,
    end_date: str,
    *,
    repo: Optional[FootfallOverrideRepository] = None,
) -> List[Dict[str, Any]]:
    """Overlay overrides onto `summaries` and inject synthetic rows for missing dates.

    `summaries` is mutated only by replacement; the returned list is sorted by
    `(date, location_id)` so callers don't need to re-sort after injection.
    """
    location_ids = list(location_ids)
    if not location_ids:
        return list(summaries)

    repo = repo or get_footfall_override_repository()
    overrides = repo.get_for_range(location_ids, start_date, end_date)
    if not overrides:
        return list(summaries)

    overrides_by_key: Dict[Tuple[int, str], Dict[str, Any]] = {
        (int(o["location_id"]), _date_str(o["date"])): o for o in overrides
    }

    out: List[Dict[str, Any]] = []
    seen_keys: set[Tuple[int, str]] = set()
    for s in summaries:
        loc = s.get("location_id")
        if loc is None:
            out.append(s)
            continue
        key = (int(loc), _date_str(s.get("date")))
        seen_keys.add(key)
        ov = overrides_by_key.get(key)
        out.append(_overlay(s, ov) if ov else s)

    # Inject synthetic rows for overrides without a matching summary.
    for key, ov in overrides_by_key.items():
        if key in seen_keys:
            continue
        loc, date = key
        out.append(_synthetic_summary(loc, date, ov))

    out.sort(key=lambda r: (_date_str(r.get("date")), int(r.get("location_id") or 0)))
    return out


def apply_override_to_single(
    summary: Optional[Dict[str, Any]],
    location_id: int,
    date: str,
    *,
    repo: Optional[FootfallOverrideRepository] = None,
) -> Optional[Dict[str, Any]]:
    """Overlay an override onto a single summary row (or build a synthetic one)."""
    repo = repo or get_footfall_override_repository()
    ov = repo.get(location_id, date)
    if ov is None:
        return summary
    if summary is None:
        return _synthetic_summary(location_id, date, ov)
    return _overlay(summary, ov)
