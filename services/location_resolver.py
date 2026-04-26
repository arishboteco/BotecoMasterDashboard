"""Canonical location alias resolver for restaurant-to-location ID mapping."""

from __future__ import annotations

from typing import Any


def _normalize_name(value: Any) -> str:
    """Return a normalized location token for dictionary lookups."""
    return " ".join(str(value or "").strip().lower().split())


def build_location_alias_map(locations: list[dict], aliases: dict[str, str]) -> dict[str, int]:
    """Build a normalized alias/name -> location_id map.

    Args:
        locations: Rows containing at least ``id`` and ``name`` keys.
        aliases: Alias-to-canonical-name mapping (usually config.RESTAURANT_NAME_MAP).

    Returns:
        Dict keyed by normalized names and aliases with integer location IDs.
    """
    alias_map: dict[str, int] = {}
    canonical_name_to_id: dict[str, int] = {}

    for location in locations:
        location_id = int(location["id"])
        normalized_name = _normalize_name(location.get("name"))
        if not normalized_name:
            continue
        canonical_name_to_id[normalized_name] = location_id
        alias_map[normalized_name] = location_id

    for alias, canonical_name in aliases.items():
        canonical_id = canonical_name_to_id.get(_normalize_name(canonical_name))
        if canonical_id is None:
            continue
        normalized_alias = _normalize_name(alias)
        if normalized_alias:
            alias_map[normalized_alias] = canonical_id

    return alias_map


def resolve_location_id(
    restaurant_name: Any,
    locations: list[dict],
    aliases: dict[str, str],
    fallback_location_id: int | None = None,
) -> int | None:
    """Resolve a location ID from a restaurant/outlet string.

    Matching order:
      1) alias map (including config-provided aliases)
      2) exact DB location names (included in the same alias map)
      3) fallback_location_id, when provided
    """
    alias_map = build_location_alias_map(locations=locations, aliases=aliases)
    resolved = alias_map.get(_normalize_name(restaurant_name))
    if resolved is not None:
        return resolved
    return fallback_location_id
