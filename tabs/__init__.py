"""Per-tab rendering modules for the Boteco Dashboard."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class TabContext:
    """Shared context passed to every tab's render() function."""

    location_id: int
    report_loc_ids: List[int]
    report_display_name: str
    all_locs: List[Dict[str, Any]]
    location_settings: Optional[Dict[str, Any]]
