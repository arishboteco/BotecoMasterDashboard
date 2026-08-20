"""Pagination helpers for Supabase/PostgREST reads.

PostgREST caps every response at a fixed row count (1000 by default on
Supabase). A plain ``.select(...).execute()`` therefore returns *only the
first page* and silently drops the rest — no error, no warning, just a
short result. Any code that then sums those rows reports a number that is
quietly too low.

Every read that can legitimately return more than a few hundred rows must
page through the result instead. :func:`fetch_all_rows` does that: it
re-runs the query with successive ``.range()`` windows and concatenates
the pages.

Ordering matters. Without a deterministic ``ORDER BY`` Postgres may return
rows in a different order for each page request, which can duplicate some
rows and skip others. Every paged query is therefore ordered by a stable
tiebreaker column (the primary key) as its *last* sort key, so any
caller-supplied ordering is preserved but ties are broken consistently.
"""

from __future__ import annotations

import time
from typing import Any, Callable, Dict, List

from boteco_logger import get_logger

logger = get_logger(__name__)

# Matches Supabase's default PostgREST `db-max-rows`. Requesting a larger
# window than the server allows would make a truncated page look like the
# final one, so never raise this above the server's cap.
DEFAULT_PAGE_SIZE = 1000

# Safety valve: stop paging rather than loop forever if the server keeps
# returning full pages (e.g. an unstable sort making offsets meaningless).
MAX_PAGES = 500


def _retryable_errors() -> tuple:
    """Transient transport errors worth retrying, if httpx is importable."""
    try:
        import httpx
    except ImportError:
        return ()
    return (httpx.ReadError,)


def execute_with_retry(query_builder: Any, *, max_attempts: int = 3) -> Any:
    """Execute a Supabase query, retrying on transient socket errors."""
    retryable = _retryable_errors()

    delay = 0.5
    for attempt in range(max_attempts):
        try:
            return query_builder.execute()
        except retryable:
            if attempt == max_attempts - 1:
                raise
            logger.warning(
                "Transient Supabase read error (attempt %d/%d), retrying in %.1fs",
                attempt + 1,
                max_attempts,
                delay,
            )
            time.sleep(delay)
            delay *= 2
    raise RuntimeError("unreachable: retry loop exhausted without returning or raising")


def fetch_all_rows(
    build_query: Callable[[], Any],
    *,
    order_by: str = "id",
    page_size: int = DEFAULT_PAGE_SIZE,
    max_attempts: int = 3,
) -> List[Dict[str, Any]]:
    """Return every row a Supabase query matches, paging past the row cap.

    Args:
        build_query: Zero-arg callable returning a *fresh* query builder.
            It is called once per page, so it must not reuse a builder that
            already carries a ``.range()``.
        order_by: Stable tiebreaker column appended as the final sort key.
            Pass ``""`` to skip (only safe when the caller already orders by
            something unique).
        page_size: Rows per request. Must not exceed the server's cap.
        max_attempts: Transient-error retries per page.

    Returns:
        The concatenated rows from every page.
    """
    if page_size < 1:
        raise ValueError("page_size must be at least 1")

    rows: List[Dict[str, Any]] = []
    offset = 0

    for _ in range(MAX_PAGES):
        query = build_query()
        if order_by:
            query = query.order(order_by)
        result = execute_with_retry(
            query.range(offset, offset + page_size - 1), max_attempts=max_attempts
        )
        page = list(result.data or [])
        if not page:
            break
        rows.extend(page)
        offset += len(page)
        # A page shorter than requested means the data ran out — which holds
        # only while page_size stays at or below the server's row cap, since
        # a capped page would otherwise look like the last one.
        if len(page) < page_size:
            break
    else:
        logger.warning(
            "fetch_all_rows stopped at the %d-page safety limit (%d rows); "
            "results may be incomplete",
            MAX_PAGES,
            len(rows),
        )

    return rows
