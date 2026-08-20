"""Tests for db.supabase_paging — PostgREST row-cap pagination.

PostgREST caps every response at 1000 rows by default. Before pagination a
month with more than 1000 category rows silently reported only the first
1000, understating MTD totals and making complete data look incomplete.
"""

from __future__ import annotations

from typing import Any, Dict, List

import pytest

from db.supabase_paging import DEFAULT_PAGE_SIZE, MAX_PAGES, fetch_all_rows


class _Result:
    def __init__(self, data):
        self.data = data


class _FakeQuery:
    """Minimal stand-in for a Supabase query builder.

    Serves rows from ``dataset``, honouring ``.range()`` and applying the
    server's row cap the way PostgREST does.
    """

    def __init__(self, dataset: List[Dict[str, Any]], server_cap: int, calls: list):
        self._dataset = dataset
        self._server_cap = server_cap
        self._calls = calls
        self._order_cols: List[str] = []
        self._start = 0
        self._end: int | None = None

    def order(self, column, **_kwargs):
        self._order_cols.append(column)
        return self

    def range(self, start, end):
        self._start, self._end = start, end
        return self

    def execute(self):
        assert self._end is not None, "range() must be applied before execute()"
        window = self._end - self._start + 1
        self._calls.append((self._start, self._end, tuple(self._order_cols)))
        rows = self._dataset[self._start : self._start + min(window, self._server_cap)]
        return _Result(list(rows))


def _dataset(n: int) -> List[Dict[str, Any]]:
    return [{"id": i, "net_amount": 1.0} for i in range(n)]


class TestFetchAllRows:
    @pytest.mark.parametrize("total", [0, 1, 999, 1000, 1001, 1203, 2500])
    def test_returns_every_row_past_the_cap(self, total):
        data = _dataset(total)
        calls: list = []

        rows = fetch_all_rows(lambda: _FakeQuery(data, DEFAULT_PAGE_SIZE, calls))

        assert [r["id"] for r in rows] == list(range(total))

    def test_july_sized_range_is_not_truncated_at_1000(self):
        # Regression: July 2026 had 1203 category rows across both outlets;
        # the un-paged read returned exactly 1000 of them.
        data = _dataset(1203)
        calls: list = []

        rows = fetch_all_rows(lambda: _FakeQuery(data, DEFAULT_PAGE_SIZE, calls))

        assert len(rows) == 1203
        assert sum(r["net_amount"] for r in rows) == 1203.0

    def test_applies_stable_order_key_for_paging(self):
        data = _dataset(1500)
        calls: list = []

        fetch_all_rows(lambda: _FakeQuery(data, DEFAULT_PAGE_SIZE, calls))

        # Every page must carry the tiebreaker, or pages can overlap/skip.
        assert all("id" in ordering for _, _, ordering in calls)

    def test_requests_successive_non_overlapping_windows(self):
        data = _dataset(2500)
        calls: list = []

        fetch_all_rows(lambda: _FakeQuery(data, DEFAULT_PAGE_SIZE, calls))

        starts = [start for start, _, _ in calls]
        assert starts == [0, 1000, 2000]

    def test_stops_after_one_request_when_under_a_page(self):
        data = _dataset(62)
        calls: list = []

        rows = fetch_all_rows(lambda: _FakeQuery(data, DEFAULT_PAGE_SIZE, calls))

        assert len(rows) == 62
        assert len(calls) == 1

    def test_custom_order_column_is_preserved(self):
        data = _dataset(10)
        calls: list = []

        fetch_all_rows(
            lambda: _FakeQuery(data, DEFAULT_PAGE_SIZE, calls).order("date"),
            order_by="id",
        )

        _, _, ordering = calls[0]
        assert ordering == ("date", "id")

    def test_rejects_invalid_page_size(self):
        with pytest.raises(ValueError):
            fetch_all_rows(lambda: _FakeQuery([], 1000, []), page_size=0)

    def test_gives_up_at_the_page_safety_limit(self):
        # A server that always returns a full page must not loop forever.
        class _Endless:
            def order(self, column, **_kwargs):
                return self

            def range(self, start, end):
                self._n = end - start + 1
                return self

            def execute(self):
                return _Result(_dataset(self._n))

        rows = fetch_all_rows(lambda: _Endless(), page_size=10)

        assert len(rows) == MAX_PAGES * 10
