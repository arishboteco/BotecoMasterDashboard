"""Per-tab rendering modules for the Boteco Dashboard."""

from dataclasses import dataclass
from typing import Any


@dataclass
class TabContext:
    """Shared context passed to every tab's render() function."""

    location_id: int
    import_loc_id: int
    report_loc_ids: list[int]
    report_display_name: str
    all_locs: list[dict[str, Any]]
    location_settings: dict[str, Any] | None
    import_location_settings: dict[str, Any] | None
