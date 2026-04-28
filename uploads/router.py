"""Routing helpers for smart upload fragments."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Optional

from services.location_resolver import build_location_alias_map


def build_restaurant_location_map(
    locations: list[dict[str, Any]], aliases: dict[str, str]
) -> dict[str, int]:
    """Build normalized restaurant/location alias map."""
    return build_location_alias_map(locations=locations, aliases=aliases)


def group_fragments_by_restaurant(
    fragments: list[dict[str, Any]],
) -> tuple[dict[str, list[dict[str, Any]]], list[dict[str, Any]]]:
    """Split fragments into tagged-by-restaurant and untagged buckets."""
    by_restaurant: dict[Optional[str], list[dict[str, Any]]] = defaultdict(list)
    for fragment in fragments:
        by_restaurant[fragment.get("restaurant")].append(fragment)

    untagged = by_restaurant.pop(None, [])
    tagged = {name: frags for name, frags in by_restaurant.items() if name}
    return tagged, untagged


def route_tagged_fragments_by_location(
    tagged_by_restaurant: dict[str, list[dict[str, Any]]],
    restaurant_to_location: dict[str, int],
    global_notes: list[str],
) -> dict[int, list[dict[str, Any]]]:
    """Map restaurant buckets to location IDs and append unknown-restaurant notes."""
    routed: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for restaurant_name, fragments in tagged_by_restaurant.items():
        loc_id = restaurant_to_location.get(" ".join(str(restaurant_name).strip().lower().split()))
        if loc_id is None:
            global_notes.append(f"Unknown restaurant '{restaurant_name}' in CSV — skipped.")
            continue
        routed[loc_id].extend(fragments)
    return dict(routed)


def route_untagged_day_results(
    location_results: dict[int, list[Any]],
    untagged_day_results: list[Any],
    fallback_location_id: int,
) -> dict[int, list[Any]]:
    """Attach untagged day results to fallback location preserving legacy behavior."""
    if not untagged_day_results:
        return location_results

    fallback_loc = fallback_location_id or next(iter(location_results), None)
    if fallback_loc is not None:
        location_results.setdefault(fallback_loc, []).extend(untagged_day_results)
    else:
        location_results.setdefault(fallback_location_id, []).extend(untagged_day_results)
    return location_results
