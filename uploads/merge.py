"""Fragment merge helpers for smart upload."""

from __future__ import annotations

from typing import Any

import boteco_logger
import pos_parser
from uploads.models import DayResult

logger = boteco_logger.get_logger(__name__)

KIND_PRIORITY = {
    "dynamic_report": 5,
    "item_order_details": 10,
    "order_summary_csv": 20,
    "flash_report": 30,
}


def merge_fragments_by_date(
    fragments: list[dict[str, Any]],
    timing_services: list[dict[str, Any]],
) -> list[DayResult]:
    """Group fragments by date, merge them, and return validated DayResult entries."""
    if not fragments:
        return []

    by_date = pos_parser.group_fragments_by_date(fragments)
    day_results: list[DayResult] = []

    for date_str in sorted(by_date.keys()):
        day_fragments = by_date[date_str]
        day_fragments.sort(key=lambda f: KIND_PRIORITY.get(f.get("file_type", ""), 100))
        source_kinds = sorted(
            {
                str(f.get("file_type"))
                for f in day_fragments
                if isinstance(f.get("file_type"), str) and f.get("file_type")
            },
            key=lambda kind: KIND_PRIORITY.get(kind, 100),
        )
        merged = pos_parser.merge_upload_fragments(day_fragments)

        if timing_services and not merged.get("services"):
            matched_timing = next(
                (timing for timing in timing_services if timing.get("date") == date_str),
                timing_services[0] if len(timing_services) == 1 else None,
            )
            if matched_timing and matched_timing.get("services"):
                merged["services"] = [
                    {"type": service["type"], "amount": service["amount"]}
                    for service in matched_timing["services"]
                ]

        if not merged.get("net_total") and merged.get("gross_total"):
            logger.warning(
                "net_total missing for %s — defaulting to gross_total (₹%s)",
                date_str,
                merged["gross_total"],
            )
            merged["net_total"] = float(merged["gross_total"])
        if not merged.get("gross_total") and merged.get("net_total"):
            logger.warning(
                "gross_total missing for %s — defaulting to net_total (₹%s)",
                date_str,
                merged["net_total"],
            )
            merged["gross_total"] = float(merged["net_total"])

        ok, errors, warnings = pos_parser.validate_data(merged)
        if warnings:
            logger.warning("Validation warnings for %s: %s", date_str, "; ".join(warnings))

        day_results.append(
            DayResult(
                date=date_str,
                merged=merged,
                source_kinds=source_kinds,
                errors=(errors if not ok else []),
                warnings=warnings,
            )
        )

    return day_results
