"""Shared date-range helpers for analytics and database boundaries."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Iterable


ISO_DATE_FORMAT = "%Y-%m-%d"


def normalize_date_str(value: object) -> str:
    """Normalize supported date-like values to YYYY-MM-DD.

    Args:
        value: A date-like value such as ISO string, ``datetime.date``,
            or ``datetime.datetime``.

    Returns:
        Normalized date string in ``YYYY-MM-DD`` format.

    Raises:
        ValueError: If the value cannot be interpreted as a date.
    """
    if isinstance(value, datetime):
        return value.date().strftime(ISO_DATE_FORMAT)
    if isinstance(value, date):
        return value.strftime(ISO_DATE_FORMAT)
    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Date string cannot be empty")

        try:
            return datetime.strptime(cleaned, ISO_DATE_FORMAT).strftime(ISO_DATE_FORMAT)
        except ValueError as exc:
            raise ValueError(f"Unsupported date format: {value!r}") from exc

    raise ValueError(f"Unsupported date value type: {type(value).__name__}")


def month_bounds(year: int, month: int) -> tuple[str, str]:
    """Return month start (inclusive) and next-month start (exclusive)."""
    start = date(year, month, 1)
    if month == 12:
        end = date(year + 1, 1, 1)
    else:
        end = date(year, month + 1, 1)
    return start.strftime(ISO_DATE_FORMAT), end.strftime(ISO_DATE_FORMAT)


def date_range_inclusive(start: object, end: object) -> Iterable[str]:
    """Yield inclusive YYYY-MM-DD dates between two boundaries."""
    start_date = datetime.strptime(normalize_date_str(start), ISO_DATE_FORMAT).date()
    end_date = datetime.strptime(normalize_date_str(end), ISO_DATE_FORMAT).date()

    if end_date < start_date:
        raise ValueError("end must be on or after start")

    current = start_date
    while current <= end_date:
        yield current.strftime(ISO_DATE_FORMAT)
        current += timedelta(days=1)
