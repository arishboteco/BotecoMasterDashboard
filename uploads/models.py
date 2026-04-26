"""Dataclasses for smart upload parsing results."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class FileResult:
    """Per-file detection and parsing outcome."""

    filename: str
    kind: str
    kind_label: str
    importable: bool
    notes: List[str] = field(default_factory=list)
    error: Optional[str] = None
    content: Optional[bytes] = None


@dataclass
class DayResult:
    """Parsed + merged data ready for one calendar date."""

    date: str
    merged: Dict[str, Any]
    source_kinds: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class SmartUploadResult:
    """Full result returned by process_smart_upload()."""

    files: List[FileResult]
    days: List[DayResult]
    global_notes: List[str] = field(default_factory=list)
    location_results: Dict[int, List[DayResult]] = field(default_factory=dict)
