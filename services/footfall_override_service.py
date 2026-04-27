"""Read-time merge helpers for manual footfall overrides."""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from repositories.footfall_override_repository import get_footfall_override_repository

_SYNTHETIC_NUMERIC_DEFAULTS = {
    "id": None,
    "covers": 0,
    "turns": 0,
    "gross_total": 0,
    "net_total": 0,
    "cash_sales": 0,
    "card_sales": 0,
    "gpay_sales": 0,
    "zomato_sales": 0,
    "other_sales": 0,
    "service_charge": 0,
    "cgst": 0,
    "sgst": 0,
    "discount": 0,
    "complimentary": 0,
    "apc": 0,
    "target": 0,
    "pct_target": 0,
    "mtd_total_covers": 0,
    "mtd_net_sales": 0,
    "mtd_discount": 0,
    "mtd_avg_daily": 0,
    "mtd_target": 0,
    "mtd_pct_target": 0,
    "lunch_covers": 0,
    "dinner_covers": 0,
    "order_count": 0,
}


def _override_key(row: Dict[str, Any]) -> Tuple[int, str]:
    return int(row.get("location_id") or 0), str(row.get("date") or "")


def _synthetic_summary(override: Dict[str, Any]) -> Dict[str, Any]:
    lunch_covers = int(override.get("lunch_covers") or 0)
    dinner_covers = int(override.get("dinner_covers") or 0)
    row = dict(_SYNTHETIC_NUMERIC_DEFAULTS)
    row.update(
        {
            "location_id": int(override["location_id"]),
            "date": str(override["date"]),
            "lunch_covers": lunch_covers,
            "dinner_covers": dinner_covers,
            "covers": lunch_covers + dinner_covers,
            "categories": [],
            "services": [],
            "_override_only": True,
        }
    )
    return row


def _apply_override_to_row(row: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(row)
    pos_lunch = int(out.get("lunch_covers") or 0)
    pos_dinner = int(out.get("dinner_covers") or 0)
    lunch_covers = override.get("lunch_covers")
    dinner_covers = override.get("dinner_covers")

    out["lunch_covers"] = pos_lunch if lunch_covers is None else int(lunch_covers)
    out["dinner_covers"] = pos_dinner if dinner_covers is None else int(dinner_covers)
    out["covers"] = int(out["lunch_covers"] or 0) + int(out["dinner_covers"] or 0)
    return out


def apply_overrides(
    summaries: List[Dict[str, Any]],
    location_ids: List[int],
    start: str,
    end: str,
) -> List[Dict[str, Any]]:
    """Overlay footfall overrides onto fetched summaries.

    Existing summary rows keep POS values for any leg whose override is NULL. If an override
    exists without a POS summary, a zero-sales synthetic row is injected and marked with
    ``_override_only=True`` for UI consumers that want to dim or label it.
    """
    if not location_ids:
        return summaries

    overrides = get_footfall_override_repository().get_for_range(location_ids, start, end)
    if not overrides:
        return summaries

    overrides_by_key = {_override_key(row): row for row in overrides}
    seen_keys = set()
    merged: List[Dict[str, Any]] = []

    for summary in summaries:
        key = _override_key(summary)
        seen_keys.add(key)
        override = overrides_by_key.get(key)
        if override is None:
            merged.append(summary)
        else:
            merged.append(_apply_override_to_row(summary, override))

    for key, override in overrides_by_key.items():
        if key not in seen_keys:
            merged.append(_synthetic_summary(override))

    return sorted(
        merged,
        key=lambda row: (str(row.get("date") or ""), int(row.get("location_id") or 0)),
    )
